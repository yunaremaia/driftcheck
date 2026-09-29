"""uv.lock content drift detection: uv.lock vs pyproject.toml version mismatches."""

from __future__ import annotations
import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def parse_uv_lock(filepath: str | Path) -> dict[str, str]:
    """Parse uv.lock TOML format.

    The file has [[package]] sections with 'name' and 'version' fields.
    Returns {package_name_lower: version_string}.
    """
    packages: dict[str, str] = {}
    try:
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
        for pkg in data.get("package", []):
            name = pkg.get("name")
            version = pkg.get("version")
            if name and version:
                packages[name.lower()] = version
    except (FileNotFoundError, PermissionError, OSError, tomllib.TOMLDecodeError):
        pass
    return packages


def parse_pyproject_uv_deps(text: str) -> dict[str, str]:
    """Parse pyproject.toml [project.dependencies] version constraints.

    Returns {package_name_lower: version_spec}.
    Handles both multi-line array format and inline array format.
    """
    deps: dict[str, str] = {}
    if not text:
        return deps

    in_deps = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        # Section header — update in_deps flag
        if stripped.startswith("["):
            in_deps = "dependencies" in stripped.lower()
            continue

        # Enter dependencies via inline array: `dependencies = ["pkg>=1", ...]`
        m = re.match(r'^dependencies\s*=\s*\[', stripped)
        if m:
            in_deps = True
            # If the closing bracket is on the same line, parse inline
            close_m = re.match(r'^dependencies\s*=\s*\[(.*)\]\s*$', stripped)
            if close_m:
                rest = close_m.group(1)
                for item in rest.split(","):
                    item = item.strip().strip("\"'")
                    if item:
                        dm = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9._-]*)(.*)$', item)
                        if dm and dm.group(1).lower() != "python":
                            deps[dm.group(1).lower()] = dm.group(2)
            continue

        if not in_deps:
            continue

        # Close bracket (multiline array)
        if stripped == "]":
            in_deps = False
            continue

        # Array entry on its own line: `"package>=version"` or `"package"`
        m = re.match(r'^["\']([a-zA-Z0-9][a-zA-Z0-9._-]*)([^"\']*)?["\']', stripped)
        if m:
            name, ver = m.group(1), m.group(2) or ""
            if name.lower() != "python":
                deps[name.lower()] = ver
            continue

        # Inline table entry: `package = "version"`
        m = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9._-]*)\s*=\s*["\']([^"\']+)["\']', stripped)
        if m:
            name, ver = m.group(1), m.group(2)
            if name.lower() != "python":
                deps[name.lower()] = ver

    return deps


def find_uv_lock_drift(root: str | Path) -> list[dict]:
    """Detect drift between uv.lock pinned versions and pyproject.toml constraints.

    Returns list of {type, package, uv_lock_version, pyproject_spec, file, message}.
    """
    root = Path(root)
    uv_lock_path = root / "uv.lock"
    pyproject_path = root / "pyproject.toml"

    if not uv_lock_path.exists():
        return []

    uv_packages = parse_uv_lock(uv_lock_path)
    if not uv_packages:
        return []

    pyproject_text = _read_text_safe(pyproject_path) or ""
    pyproject_deps = parse_pyproject_uv_deps(pyproject_text)

    drifts: list[dict] = []
    for pkg_name, uv_version in uv_packages.items():
        if pkg_name in pyproject_deps:
            pyproject_spec = pyproject_deps[pkg_name]
            drifts.append({
                "type": "uv_lock_drift",
                "package": pkg_name,
                "uv_lock_version": uv_version,
                "pyproject_spec": pyproject_spec,
                "file": "uv.lock",
                "message": f"{pkg_name}: uv.lock={uv_version}, pyproject.toml={pyproject_spec}",
            })

    return drifts


def _read_text_safe(path: Path) -> str | None:
    """Read text file safely, returning None if missing or unreadable."""
    try:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
