"""Python dependency freshness detector: pinned versions vs PyPI latest.

Detects when version pins in requirements.txt and pyproject.toml
are stale compared to the latest version available on PyPI.
"""
from __future__ import annotations
import re
from packaging import version as pkg_version
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json as json_mod


# Match package==version in requirements.txt
REQ_PINNED_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*(?P<ver>[^\s#]+)',
    re.MULTILINE,
)

# Match package = "version" in pyproject.toml simple key-value form (tool.poetry.dependencies style)
PYPROJECT_SIMPLE_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9][A-Za-z0-9._-]*)\s*=\s*["\'][=<>~^]?(?P<ver>[^"\']+)["\']',
    re.MULTILINE,
)

# Match quoted dependency entries in pyproject.toml [project] dependencies list: "pkg==1.0"
PYPROJECT_LIST_RE = re.compile(
    r'^\s*\[?["\'](?P<pkg>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<spec>[=<>~^]+)(?P<ver>[0-9][^"\']*)["\']\]?\s*,?\s*$',
    re.MULTILINE,
)


def parse_pinned_requirements(text: str) -> dict[str, str]:
    """Parse pinned packages from requirements.txt (== only — freshness requires exact pins).

    Returns dict of {package_name: version_string}.
    Only == pins are checked for freshness; >=, ~=, != cannot be freshness-checked.
    """
    pkgs: dict[str, str] = {}
    for m in REQ_PINNED_RE.finditer(text):
        pkg = m.group("pkg").lower().replace("_", "-")
        ver = m.group("ver").strip()
        if pkg in ("pip", "setuptools", "wheel", "python", "packaging"):
            continue
        pkgs[pkg] = ver
    return pkgs


def parse_pinned_pyproject(text: str) -> dict[str, str]:
    """Parse pinned packages from pyproject.toml dependencies.

    Looks in [project] dependencies (list of quoted strings) and
    [tool.poetry.dependencies] sections (simple key-value form).
    Only handles == pins and caret/tilde constraints that resolve to a minimum version.

    Returns dict of {package_name: version_string}.
    """
    pkgs: dict[str, str] = {}

    # Find dependency sections
    in_deps = False
    current_section = ""
    expect_list_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            current_section = stripped.lower()
            in_deps = "dependenc" in current_section
            expect_list_deps = current_section == "[project]"  # [project] has dependencies = [...]
            continue
        if not in_deps and not expect_list_deps:
            continue

        # Handle [project] dependencies = ["pkg==1.0", ...] list form
        if expect_list_deps and not in_deps:
            if stripped.startswith("dependencies") and "=" in stripped:
                # Check if the list is on the same line: dependencies = ["pkg==1.0"]
                if "[" in stripped and "]" in stripped:
                    # Extract the inline list content
                    start = stripped.index("[")
                    end = stripped.index("]") + 1
                    list_content = stripped[start:end]
                    for m in PYPROJECT_LIST_RE.finditer(list_content):
                        pkg = m.group("pkg").lower().replace("_", "-")
                        spec = m.group("spec")
                        ver = m.group("ver").strip()
                        if pkg in ("python", "requires", "project"):
                            continue
                        if spec == "==":
                            pkgs[pkg] = ver
                        elif spec in ("^", "~"):
                            pkgs[pkg] = ver
                        elif spec == ">=":
                            pkgs[pkg] = ver
                    in_deps = True
                    expect_list_deps = False
                    continue
                in_deps = True
                expect_list_deps = False
            continue

        # Try list form first: "pkg==1.0" or "pkg>=1.0"
        m = PYPROJECT_LIST_RE.match(stripped)
        if m:
            pkg = m.group("pkg").lower().replace("_", "-")
            spec = m.group("spec")
            ver = m.group("ver").strip()
            if pkg in ("python", "requires", "project"):
                continue
            if spec == "==":
                pkgs[pkg] = ver
            elif spec in ("^", "~", "~=", ">="):
                pkgs[pkg] = ver
            continue

        # Try simple key-value form: pkg = "^1.0" or pkg = "==1.0"
        m = PYPROJECT_SIMPLE_RE.match(stripped)
        if m:
            pkg = m.group("pkg").lower().replace("_", "-")
            ver = m.group("ver").strip()
            if pkg in ("python", "requires", "project"):
                continue
            # Strip leading '=' from version (e.g. "=2.28.0" -> "2.28.0")
            if ver.startswith("=") and not ver.startswith("=="):
                ver = ver[1:]
            if ver.startswith("=="):
                pkgs[pkg] = ver[2:]
            elif ver.startswith("^") or ver.startswith("~"):
                pkgs[pkg] = ver[1:]
            elif ver.startswith(">="):
                pkgs[pkg] = ver[2:]
            elif ver and not ver.startswith(("<", ">", "!=", "*")):
                pkgs[pkg] = ver

    return pkgs


def _parse_version(v: str) -> pkg_version.Version | None:
    """Parse a version string, returning None for unparseable."""
    try:
        return pkg_version.parse(v)
    except (pkg_version.InvalidVersion, TypeError):
        return None


def _fetch_pypi_latest(package: str) -> str | None:
    """Fetch the latest version of a package from PyPI JSON API.

    Returns the version string or None on failure.
    """
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json_mod.load(resp)
            return data.get("info", {}).get("version")
    except (URLError, HTTPError, json_mod.JSONDecodeError, OSError):
        return None


def find_python_dep_freshness(
    requirements_text: str,
    pyproject_text: str,
    *,
    offline: bool = False,
    cache: dict[str, str] | None = None,
) -> list[dict]:
    """Detect stale Python dependency pins vs PyPI latest.

    Checks requirements.txt and pyproject.toml for pinned versions
    that are behind the latest release on PyPI.

    Args:
        requirements_text: contents of requirements.txt
        pyproject_text: contents of pyproject.toml
        offline: if True, skip PyPI network lookups (useful for CI without internet)
        cache: optional dict of {package: latest_version} to use instead of fetching

    Returns list of {file, package, pinned_version, latest_version, pos}.
    """
    if offline and cache is None:
        return []

    req_pkgs = parse_pinned_requirements(requirements_text)
    pp_pkgs = parse_pinned_pyproject(pyproject_text)

    all_pkgs: dict[str, tuple[str, str]] = {}  # pkg -> (version, source_file)
    for pkg, ver in req_pkgs.items():
        all_pkgs[pkg] = (ver, "requirements.txt")
    for pkg, ver in pp_pkgs.items():
        if pkg not in all_pkgs:
            all_pkgs[pkg] = (ver, "pyproject.toml")

    drifts: list[dict] = []
    for pkg, (pinned_ver, source_file) in sorted(all_pkgs.items()):
        pinned_parsed = _parse_version(pinned_ver)
        if pinned_parsed is None:
            continue

        latest_ver: str | None = None
        if cache and pkg in cache:
            latest_ver = cache[pkg]
        elif not offline:
            latest_ver = _fetch_pypi_latest(pkg)

        if latest_ver is None:
            continue

        latest_parsed = _parse_version(latest_ver)
        if latest_parsed is None:
            continue

        if latest_parsed > pinned_parsed:
            drifts.append({
                "file": source_file,
                "package": pkg,
                "pinned_version": pinned_ver,
                "latest_version": latest_ver,
                "pos": 0,
            })

    return drifts
