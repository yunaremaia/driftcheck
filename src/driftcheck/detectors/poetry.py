"""Poetry pyproject.toml drift detection: pyproject.toml vs README."""
from __future__ import annotations
import re

# Match pyproject.toml [tool.poetry.dependencies] and [tool.poetry.dev-dependencies]
POETRY_PYTHON_RE = re.compile(
    r'python\s*=\s*["\^~>=<]*\s*([\d.]+)',
    re.MULTILINE,
)
POETRY_PKG_RE = re.compile(
    r'([a-zA-Z0-9_-]+)\s*=\s*["\']?[\^~>=<]*\s*([\d.]+)',
    re.MULTILINE,
)
# Match README Python version mentions: "Python 3.12", "Python >=3.11", "requires Python 3.10"
README_PYTHON_RE = re.compile(
    r'[Pp]ython\s*[>=~^]*\s*(\d+\.\d+(?:\.\d+)?)',
)
# Match README package mentions: "numpy 1.24", "requires numpy>=1.26", "uses pandas 2.0"
README_PKG_RE = re.compile(
    r'([a-zA-Z0-9_-]+)\s*[>=~^]*\s*(\d+\.\d+(?:\.\d+)?)',
)


def parse_poetry_pyproject(text: str) -> dict[str, str]:
    """Parse pyproject.toml for Poetry dependencies.

    Returns dict of {package_name: version_string} including 'python' key.
    Handles [tool.poetry.dependencies] and [tool.poetry.dev-dependencies] sections.
    """
    pkgs: dict[str, str] = {}
    lines = text.splitlines()
    in_poetry_deps = False
    in_project_deps = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if "poetry" in stripped.lower() and "dependenc" in stripped.lower():
                in_poetry_deps = True
                in_project_deps = False
            elif "project.dependenc" in stripped.lower():
                in_project_deps = True
                in_poetry_deps = False
            else:
                in_poetry_deps = False
                in_project_deps = False
            continue

        if in_poetry_deps or in_project_deps:
            # Special case: python = "^3.12"
            m = POETRY_PYTHON_RE.match(stripped)
            if m:
                pkgs["python"] = m.group(1)
                continue

            m = POETRY_PKG_RE.match(stripped)
            if m:
                name, ver = m.group(1), m.group(2)
                if name not in ("python", "requires", "source"):
                    pkgs[name.lower()] = ver

    return pkgs


def find_poetry_drift(
    pyproject_text: str,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between Poetry pyproject.toml and README/docs.

    Checks:
    1. Python version in pyproject.toml vs README mentions
    2. Package versions in pyproject.toml vs README mentions

    Returns list of {file, package, doc_version, pyproject_version, pos}.
    """
    poetry_pkgs = parse_poetry_pyproject(pyproject_text)
    if not poetry_pkgs:
        return []

    drifts: list[dict] = []

    for fname, content in docs.items():
        # Check Python version drift
        if "python" in poetry_pkgs:
            py_pyver = poetry_pkgs["python"]
            for m in README_PYTHON_RE.finditer(content):
                doc_ver = m.group(1)
                if _major_minor(py_pyver) != _major_minor(doc_ver):
                    drifts.append({
                        "file": fname,
                        "package": "python",
                        "doc_version": doc_ver,
                        "pyproject_version": py_pyver,
                        "pos": m.start(),
                    })

        # Check package version drift
        for pkg, pp_ver in poetry_pkgs.items():
            if pkg == "python":
                continue
            pkg_pattern = re.compile(
                rf'{re.escape(pkg)}\s*[>=~^]*\s*(\d+\.\d+(?:\.\d+)?)',
                re.IGNORECASE,
            )
            for m in pkg_pattern.finditer(content):
                doc_ver = m.group(1)
                if _major_minor(pp_ver) != _major_minor(doc_ver):
                    drifts.append({
                        "file": fname,
                        "package": pkg,
                        "doc_version": doc_ver,
                        "pyproject_version": pp_ver,
                        "pos": m.start(),
                    })

    return drifts


def _major_minor(v: str) -> tuple[str, str]:
    """Extract (major, minor) from version string."""
    parts = v.split(".")
    return parts[0], parts[1] if len(parts) > 1 else "0"
