"""Pipfile drift detection: Pipfile vs Pipfile.lock version mismatches."""

import re
from pathlib import Path

PIPFILE_RE = re.compile(r'\s*([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']')
PIPFILE_LOCK_RE = re.compile(r'\s*"([a-zA-Z0-9_-]+)":\s*\{\s*"version":\s*"([^"]+)"')


def parse_pipfile_versions(filepath):
    """Parse Pipfile and return dict of package -> version spec."""
    versions = {}
    try:
        content = Path(filepath).read_text()
        for match in PIPFILE_RE.finditer(content):
            pkg, ver = match.groups()
            if pkg not in ('source', 'requires', 'pipfile'):
                versions[pkg.lower()] = ver
    except (FileNotFoundError, PermissionError):
        pass
    return versions


def parse_pipfile_lock_versions(filepath):
    """Parse Pipfile.lock and return dict of package -> version."""
    versions = {}
    try:
        content = Path(filepath).read_text()
        for match in PIPFILE_LOCK_RE.finditer(content):
            pkg, ver = match.groups()
            versions[pkg.lower()] = ver
    except (FileNotFoundError, PermissionError):
        pass
    return versions


def find_pipfile_drift(root_path):
    """Find version drift between Pipfile and Pipfile.lock."""
    root = Path(root_path)
    pipfile = root / "Pipfile"
    pipfile_lock = root / "Pipfile.lock"
    
    if not pipfile.exists() or not pipfile_lock.exists():
        return []
    
    pipfile_versions = parse_pipfile_versions(pipfile)
    lock_versions = parse_pipfile_lock_versions(pipfile_lock)
    
    drifts = []
    for pkg, pipfile_ver in pipfile_versions.items():
        if pkg in lock_versions:
            lock_ver = lock_versions[pkg]
            # Normalize versions for comparison (remove ==, >=, etc.)
            pipfile_clean = re.sub(r'^[><=!~]+', '', pipfile_ver).strip()
            lock_clean = re.sub(r'^[><=!~]+', '', lock_ver).strip()
            if pipfile_clean != lock_clean and '*' not in pipfile_ver:
                drifts.append({
                    "type": "pipfile_drift",
                    "package": pkg,
                    "pipfile_version": pipfile_ver,
                    "lock_version": lock_ver,
                    "file": "Pipfile",
                    "message": f"{pkg}: Pipfile={pipfile_ver}, Pipfile.lock={lock_ver}",
                })
    return drifts

