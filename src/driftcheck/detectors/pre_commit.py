"""Pre-commit config drift detection: .pre-commit-config.yaml rev vs README."""
from __future__ import annotations
import re
from pathlib import Path

# Single pattern to match pre-commit version mentions in docs
PRE_COMMIT_RE = re.compile(r'pre-commit\s+v?(\d+(?:\.\d+)*)', re.I)

# Match rev: lines in .pre-commit-config.yaml
REV_RE = re.compile(r'^\s+rev:\s*v?(\S+)', re.MULTILINE)

# Match repo: lines to get repo names
REPO_RE = re.compile(r'^\s+- repo:\s*(\S+)', re.MULTILINE)


def parse_pre_commit_revs(text: str) -> dict[str, str]:
    """Parse .pre-commit-config.yaml to extract {repo: rev} mappings."""
    if not text.strip():
        return {}

    repos = {}
    lines = text.splitlines()
    current_repo = None

    for line in lines:
        repo_match = REPO_RE.match(line)
        if repo_match:
            current_repo = repo_match.group(1)
            continue

        rev_match = REV_RE.match(line)
        if rev_match and current_repo:
            repos[current_repo] = rev_match.group(1)
            current_repo = None  # Only capture first rev per repo

    return repos


def _is_pre_commit_repo(repo_url: str) -> bool:
    """Check if a repo URL is pre-commit related."""
    return "pre-commit" in repo_url.lower()


def find_pre_commit_drift(pre_commit_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between .pre-commit-config.yaml rev and README mentions.

    Returns list of {file, repo, doc_version, rev, pos}.
    """
    if not pre_commit_text.strip():
        return []

    revs = parse_pre_commit_revs(pre_commit_text)
    if not revs:
        return []

    drifts = []

    for repo, rev in revs.items():
        # Only compare pre-commit-related repos against the pre-commit pattern
        if not _is_pre_commit_repo(repo):
            continue

        # Clean rev: remove trailing commas, hashes, etc.
        rev_clean = re.sub(r'[,;#].*$', '', rev).strip()
        rev_major = rev_clean.split('.')[0] if rev_clean else None

        if not rev_major:
            continue

        for fname, content in docs.items():
            for m in PRE_COMMIT_RE.finditer(content):
                doc_version = m.group(1)
                doc_major = doc_version.split('.')[0] if doc_version else None

                if doc_major and rev_major != doc_major:
                    drifts.append({
                        "file": fname,
                        "repo": repo,
                        "doc_version": doc_version,
                        "rev": rev_clean,
                        "pos": m.start(),
                    })

    return drifts
