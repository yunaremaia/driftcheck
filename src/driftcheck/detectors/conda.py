"""Conda environment drift detection: environment.yml vs installed packages."""

import re
from pathlib import Path

CONDA_ENV_RE = re.compile(r'^\s*-\s*([a-zA-Z0-9_-]+)([>=!~<]+)?([0-9.]+)?', re.MULTILINE)


def parse_conda_environment(filepath):
    """Parse environment.yml and return dict of package -> version spec."""
    versions = {}
    try:
        content = Path(filepath).read_text()
        for match in CONDA_ENV_RE.finditer(content):
            pkg = match.group(1)
            op = match.group(2) or ''
            ver = match.group(3) or ''
            if pkg not in ('python', 'pip', 'conda', 'setuptools'):
                versions[pkg.lower()] = f"{op}{ver}".strip()
    except (FileNotFoundError, PermissionError):
        pass
    return versions


def find_conda_drift(root_path):
    """Find drift in Conda environment.yml."""
    root = Path(root_path)
    env_file = root / "environment.yml"
    
    if not env_file.exists():
        return []
    
    env_versions = parse_conda_environment(env_file)
    
    drifts = []
    for pkg, ver in env_versions.items():
        if not ver:
            drifts.append({
                "type": "conda_drift",
                "package": pkg,
                "environment_version": "unpinned",
                "file": "environment.yml",
                "message": f"{pkg}: unpinned version in environment.yml",
            })
    return drifts

