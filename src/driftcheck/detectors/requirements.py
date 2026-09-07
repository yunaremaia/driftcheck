"""Python requirements.txt drift detection: requirements.txt vs pyproject.toml and README."""
from __future__ import annotations
import re

# Match package lines in requirements.txt: pkg==1.2.3, pkg>=1.2, pkg~=1.2.3, pkg!=1.0
REQUIREMENTS_PKG_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9_-]+)\s*(?:==|>=|~=|!=|>|<|<=)\s*(?P<ver>[\d.]+)',
    re.MULTILINE,
)
# Match package mentions in docs: "package 1.2.3" or "package==1.2.3"
DOC_PKG_RE = re.compile(
    r'(?P<pkg>[A-Za-z0-9_-]+)\s*(?:==\s*)?(?P<ver>\d+\.\d+(?:\.\d+)?)',
    re.MULTILINE,
)
# Match pyproject.toml tool.poetry.dependencies or [project] dependencies
PYPROJECT_PKG_RE = re.compile(
    r'(?P<pkg>[A-Za-z0-9_-]+)\s*=\s*["\']?[\^~>=<]*\s*(?P<ver>[\d.]+)',
    re.MULTILINE,
)


def parse_requirements_packages(text: str) -> dict[str, str]:
    """Parse requirements.txt content to extract package versions.

    Returns dict of {package_name: version_string}.
    Handles: pkg==1.2.3, pkg>=1.2, pkg~=1.2.3, pkg!=1.0, pkg, pkg>1.0
    """
    pkgs = {}
    for m in REQUIREMENTS_PKG_RE.finditer(text):
        pkg = m.group("pkg").lower()
        # Skip common non-package lines
        if pkg in ("pip", "setuptools", "wheel", "python"):
            continue
        pkgs[pkg] = m.group("ver")
    return pkgs


def parse_pyproject_packages(text: str) -> dict[str, str]:
    """Parse pyproject.toml content to extract package versions from dependencies.

    Looks for [tool.poetry.dependencies] and [project.dependencies] sections.
    Returns dict of {package_name: version_string}.
    """
    pkgs = {}
    # Find dependencies sections
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "dependenc" in stripped.lower():
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps:
            m = PYPROJECT_PKG_RE.match(stripped)
            if m:
                pkg = m.group("pkg").lower()
                if pkg in ("python", "requires"):
                    continue
                pkgs[pkg] = m.group("ver")
    return pkgs


def _major_minor(v: str) -> tuple[str, str]:
    """Extract (major, minor) from version string."""
    parts = v.split(".")
    return parts[0], parts[1] if len(parts) > 1 else "0"


def find_requirements_drift(
    req_text: str,
    pyproject_text: str,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between requirements.txt, pyproject.toml, and README.

    Checks:
    1. requirements.txt vs pyproject.toml (same package, different version)
    2. requirements.txt vs README mentions

    Returns list of {file, package, doc_version, requirements_version, pos}.
    """
    req_pkgs = parse_requirements_packages(req_text)
    if not req_pkgs:
        return []

    drifts = []
    pyproject_pkgs = parse_pyproject_packages(pyproject_text)

    # Check requirements.txt vs pyproject.toml
    for pkg, req_ver in req_pkgs.items():
        if pkg in pyproject_pkgs:
            pp_ver = pyproject_pkgs[pkg]
            if _major_minor(req_ver) != _major_minor(pp_ver):
                drifts.append({
                    "file": "requirements.txt",
                    "package": pkg,
                    "doc_version": pp_ver,
                    "requirements_version": req_ver,
                    "pos": 0,
                })

    # Check requirements.txt vs README mentions
    for pkg, req_ver in req_pkgs.items():
        for fname, content in docs.items():
            for m in DOC_PKG_RE.finditer(content):
                doc_pkg = m.group("pkg").lower()
                if doc_pkg == pkg:
                    doc_ver = m.group("ver")
                    if _major_minor(req_ver) != _major_minor(doc_ver):
                        drifts.append({
                            "file": fname,
                            "package": pkg,
                            "doc_version": doc_ver,
                            "requirements_version": req_ver,
                            "pos": m.start(),
                        })

    return drifts
