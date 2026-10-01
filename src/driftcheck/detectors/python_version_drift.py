"""Python version drift detection: .python-version, setup.py/setup.cfg, and GitHub Actions setup-python."""

from __future__ import annotations
import re
from pathlib import Path

# Match version strings like "3.12", "3.12.5", "3.13.0rc1"
_VERSION_RE = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?")
_PRERELEASE_RE = re.compile(r"(a|b|rc)\d*$", re.I)

# Match setup-python action with python-version input
SETUP_PYTHON_RE = re.compile(
    r"uses:\s*actions/setup-python\s*@[vV]?\d+"
    r".*?python-version\s*[:=]\s*['\"]?(?P<ver>\d+\.\d+)['\"]?",
    re.I | re.DOTALL,
)

# Match pyproject.toml/ setup.cfg/ setup.py requires-python or python_requires
_REQUIRES_RE = re.compile(
    r"(?:requires-python|python_requires)\s*=\s*['\"]?[>=~<]*\s*(?P<ver>\d+\.\d+(?:\.\d+)?)",
    re.I,
)


def _normalize(v: str) -> tuple[int, int, int]:
    """Normalize version string to (major, minor, patch) tuple."""
    v = v.strip()
    if re.match(r"^\d+$", v):
        return (int(v), 0, 0)
    m = _VERSION_RE.match(v)
    if not m:
        return (0, 0, 0)
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch")) if m.group("patch") else 0
    return (major, minor, patch)


def _strip_prerelease(v: str) -> str:
    """Strip pre-release suffix for comparison (e.g. 3.13.0rc1 -> 3.13.0)."""
    return _PRERELEASE_RE.sub("", v).strip()


def parse_python_version_file(text: str) -> tuple[int, int, int] | None:
    """Parse .python-version file content, returning normalized (major, minor, patch) or None."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line[:line.index("#")].strip()
        line = _strip_prerelease(line)
        v = _normalize(line)
        if v != (0, 0, 0):
            return v
    return None


def parse_requires_python(text: str) -> tuple[int, int, int] | None:
    """Parse requires-python / python_requires from pyproject.toml, setup.cfg, or setup.py.

    Returns the floor version (major, minor, patch) or None.
    """
    m = _REQUIRES_RE.search(text)
    if m:
        return _normalize(m.group("ver"))
    return None


def _floor_from_sources(
    pyproject_text: str | None,
    setup_cfg_text: str | None,
    setup_py_text: str | None,
) -> tuple[tuple[int, int, int] | None, str | None]:
    """Determine the Python version floor from pyproject.toml, setup.cfg, or setup.py.

    Returns (floor_tuple, source_name). pyproject.toml takes precedence.
    """
    if pyproject_text:
        floor = parse_requires_python(pyproject_text)
        if floor is not None:
            return floor, "pyproject.toml"
    if setup_cfg_text:
        floor = parse_requires_python(setup_cfg_text)
        if floor is not None:
            return floor, "setup.cfg"
    if setup_py_text:
        floor = parse_requires_python(setup_py_text)
        if floor is not None:
            return floor, "setup.py"
    return None, None


def _python_version_from_workflow(text: str) -> tuple[int, int, int] | None:
    """Extract Python version from a setup-python action step in a workflow file.

    Looks for: uses: actions/setup-python@X\n        with:\n          python-version: '3.10'
    Returns normalized version tuple or None.
    """
    for m in SETUP_PYTHON_RE.finditer(text):
        ver = m.group("ver")
        v = _normalize(ver)
        if v != (0, 0, 0):
            return v
    return None


def _find_doc_floor(docs: dict[str, str]) -> tuple[int, int, int] | None:
    """Find the highest Python version mentioned across all doc files.

    Used as a fallback floor when no pyproject.toml, setup.cfg, or setup.py is present.
    Scans all doc file contents for 'Python X.Y' mentions and returns the highest version.
    """
    PY_RE = re.compile(r"Python\s+(?P<ver>\d+\.\d+)", re.I)
    highest: tuple[int, int, int] | None = None
    for content in docs.values():
        for m in PY_RE.finditer(content):
            v = _normalize(m.group("ver"))
            if v != (0, 0, 0) and (highest is None or v > highest):
                highest = v
    return highest


def _resolve_floor(
    root: Path,
    pyproject_text: str | None,
    setup_cfg_text: str | None,
    setup_py_text: str | None,
    docs: dict[str, str],
) -> tuple[tuple[int, int, int], str]:
    """Resolve the Python version floor using the precedence:

    1. pyproject.toml / setup.cfg / setup.py (explicit source of truth)
    2. .python-version file (environment pin, when no explicit manifest)
    3. Highest Python version mentioned in doc files (least reliable, fallback)
    """
    floor, floor_source = _floor_from_sources(pyproject_text, setup_cfg_text, setup_py_text)
    if floor is not None:
        return floor, floor_source

    # Fallback 1: .python-version file
    python_version_path = root / ".python-version"
    if python_version_path.is_file():
        try:
            pv_text = python_version_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pv_text = ""
        pin = parse_python_version_file(pv_text)
        if pin is not None:
            return pin, ".python-version"

    # Fallback 2: highest Python version mentioned in docs
    doc_floor = _find_doc_floor(docs)
    if doc_floor is not None:
        return doc_floor, "doc"

    raise ValueError("No Python version floor could be resolved")


def find_python_version_drift(
    root: Path,
    pyproject_text: str | None,
    setup_cfg_text: str | None,
    setup_py_text: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect Python version drift across .python-version files, setup.py/setup.cfg,
    GitHub Actions setup-python steps, and documentation.

    Returns list of drift dicts. Each drift has:
      - file: source file (e.g. ".python-version", ".github/workflows/ci.yml", "README.md")
      - type: "version_file", "workflow", or "doc"
      - tool: "Python"
      - doc_version: the version found in the drifting file (for doc and version_file types)
      - version_file: the resolved floor version (for CLI compat)
      - pin_version: the .python-version pin (for version_file type)
      - workflow_version: the workflow setup-python version (for workflow type)
      - floor_version: the floor version string
      - floor_source: which source provided the floor
      - pos: character offset in the drifting file
    """
    drifts: list[dict] = []

    # Resolve the authoritative floor
    try:
        floor, floor_source = _resolve_floor(root, pyproject_text, setup_cfg_text, setup_py_text, docs)
    except ValueError:
        return drifts  # No floor to compare against

    floor_tuple: tuple[int, ...] = floor
    floor_str = f"{floor[0]}.{floor[1]}.{floor[2]}"

    # 1. .python-version file drift
    python_version_path = root / ".python-version"
    if python_version_path.is_file():
        try:
            pv_text = python_version_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pv_text = ""
        pin = parse_python_version_file(pv_text)
        if pin is not None and pin < floor_tuple:
            pin_str = f"{pin[0]}.{pin[1]}.{pin[2]}"
            drifts.append({
                "file": ".python-version",
                "type": "version_file",
                "tool": "Python",
                "doc_version": pin_str,
                "version_file": pin_str,
                "pin_version": pin_str,
                "floor_version": floor_str,
                "floor_source": floor_source,
                "pos": 0,
            })

    # 2. GitHub Actions setup-python workflow drift
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        for wf in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
            try:
                text = wf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = wf.relative_to(root).as_posix()
            wf_ver = _python_version_from_workflow(text)
            if wf_ver is not None and wf_ver < floor_tuple:
                wf_ver_str = f"{wf_ver[0]}.{wf_ver[1]}.{wf_ver[2]}"
                drifts.append({
                    "file": rel,
                    "type": "workflow",
                    "tool": "Python",
                    "workflow_version": wf_ver_str,
                    "doc_version": wf_ver_str,
                    "floor_version": floor_str,
                    "floor_source": floor_source,
                    "pos": 0,
                })

    # 3. Documentation drift (doc mentions a version below the floor)
    PY_RE = re.compile(r"Python\s+(?P<ver>\d+\.\d+)", re.I)
    for fname, content in docs.items():
        for m in PY_RE.finditer(content):
            doc_ver_str = m.group("ver")
            doc_ver = _normalize(doc_ver_str)
            if doc_ver < floor_tuple:
                drifts.append({
                    "file": fname,
                    "type": "doc",
                    "tool": "Python",
                    "doc_version": doc_ver_str,
                    "version_file": floor_str,
                    "floor_version": floor_str,
                    "floor_source": floor_source,
                    "pos": m.start(),
                })
                break  # one drift per doc file

    return drifts
