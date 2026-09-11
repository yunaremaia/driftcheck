"""Git tag drift detection: latest git tag vs README version mentions.

Detects when the README or docs reference a version that doesn't match
the latest git tag in the repository.
"""
from __future__ import annotations
import re

# Match version mentions in README
VERSION_TAG_RE = re.compile(
    r'(?:version|v)\s*[:=]?\s*(?P<version>\d+\.\d+(?:\.\d+)?)',
    re.I,
)
SEMVER_RE = re.compile(r'^v?(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?$')


def get_latest_git_tag(root) -> str | None:
    """Return the latest semantic version git tag, or None."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        
        # Find first semver tag
        for tag in result.stdout.splitlines():
            tag = tag.strip()
            if SEMVER_RE.match(tag):
                return tag
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def parse_semver(version: str) -> tuple[int, int, int] | None:
    """Parse version string to (major, minor, patch) tuple."""
    m = SEMVER_RE.match(version.lstrip('v'))
    if not m:
        return None
    return (
        int(m.group('major')),
        int(m.group('minor')),
        int(m.group('patch') or 0),
    )


def find_git_tag_drift(root, docs: dict[str, str]) -> list[dict]:
    """Detect drift between latest git tag and README mentions."""
    latest_tag = get_latest_git_tag(root)
    if not latest_tag:
        return []
    
    latest_version = latest_tag.lstrip('v')
    latest_parsed = parse_semver(latest_version)
    if not latest_parsed:
        return []
    
    drifts = []
    for doc_fname, doc_content in docs.items():
        for m in VERSION_TAG_RE.finditer(doc_content):
            doc_ver = m.group("version")
            doc_parsed = parse_semver(doc_ver)
            
            if not doc_parsed:
                continue
            
            # Check if versions differ
            if doc_parsed != latest_parsed:
                drifts.append({
                    "file": doc_fname,
                    "doc_version": doc_ver,
                    "git_tag": latest_tag,
                    "detail": f"README mentions version {doc_ver} but latest git tag is {latest_tag}",
                    "pos": m.start(),
                })
    
    return drifts
