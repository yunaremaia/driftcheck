"""Python version file drift detection: .python-version vs pyproject.toml requires-python.

Detects when pyenv/asdf `.python-version` pins a version below the floor declared
in `pyproject.toml` `requires-python` — creating silent breakage for anyone using
the pin file while CI uses the floor.
"""
from __future__ import annotations
import re

# Match version strings like "3.12", "3.12.5", "3.13.0rc1"
VERSION_RE = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?")
# Pre-release suffixes to strip for comparison
PRERELEASE_RE = re.compile(r"(a|b|rc)\d*$", re.I)


def _normalize_version(v: str) -> tuple[int, int, int]:
    """Normalize a version string to (major, minor, patch) tuple.

    Handles: "3.12" → (3, 12, 0), "3.13.0rc1" → (3, 13, 0), "3" → (3, 0, 0).
    """
    v = v.strip()
    # Handle major-only (e.g., "3")
    if re.match(r"^\d+$", v):
        return (int(v), 0, 0)
    m = VERSION_RE.match(v)
    if not m:
        return (0, 0, 0)
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch")) if m.group("patch") else 0
    return (major, minor, patch)


def parse_python_version_file(text: str) -> tuple[int, int, int] | None:
    """Parse .python-version file content.

    Format: one version string per line, optional comments (#), optional leading/trailing whitespace.
    Returns normalized (major, minor, patch) or None if unparseable.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments
        if "#" in line:
            line = line[: line.index("#")].strip()
        # Remove pre-release suffix for comparison
        line = PRERELEASE_RE.sub("", line)
        v = _normalize_version(line)
        if v != (0, 0, 0):
            return v
    return None


def parse_requires_python(text: str) -> tuple[int, int, int] | None:
    """Parse requires-python from pyproject.toml / setup.cfg.

    Handles: ">=3.10", ">=3.10,<3.13", "~=3.11", "==3.12".
    Returns the floor version (major, minor, patch).
    """
    # Match requires-python = ">=3.10" or ">=3.10,<3.13"
    m = re.search(r'requires-python\s*=\s*["\']?[>=~<]*\s*(\d+\.\d+(?:\.\d+)?)', text)
    if m:
        return _normalize_version(m.group(1))
    # Also check setup.cfg / setup.py: python_requires = ">=3.8" or python_requires = >=3.8
    m = re.search(r'python_requires\s*=\s*["\']?[>=~<]*\s*(\d+\.\d+(?:\.\d+)?)', text)
    if m:
        return _normalize_version(m.group(1))
    return None


def find_python_version_file_drift(
    python_version_text: str | None,
    pyproject_text: str | None,
    setup_cfg_text: str | None = None,
    setup_py_text: str | None = None,
) -> list[dict]:
    """Detect drift between .python-version and requires-python floor.

    Returns list of drift dicts. Empty list means no drift.

    Drift occurs when .python-version pins a version strictly below the
    requires-python floor — meaning the pin file would break for users.
    """
    drifts: list[dict] = []

    if not python_version_text:
        return drifts  # Detector is opt-in

    pin = parse_python_version_file(python_version_text)
    if pin is None:
        return drifts  # Unparseable — informational, not blocking

    # Determine floor from pyproject.toml, setup.cfg, or setup.py (in order of modern precedence)
    floor = None
    source = None
    if pyproject_text:
        floor = parse_requires_python(pyproject_text)
        source = "pyproject.toml"
    if floor is None and setup_cfg_text:
        floor = parse_requires_python(setup_cfg_text)
        source = "setup.cfg"
    if floor is None and setup_py_text:
        floor = parse_requires_python(setup_py_text)
        source = "setup.py"

    if floor is None:
        return drifts  # No floor to compare against

    if pin < floor:
        drifts.append(
            {
                "pin_version": f"{pin[0]}.{pin[1]}.{pin[2]}",
                "floor_version": f"{floor[0]}.{floor[1]}.{floor[2]}",
                "floor_source": source,
                "pin_file": ".python-version",
            }
        )

    return drifts
