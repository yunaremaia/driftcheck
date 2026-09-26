"""Detect GitHub Actions version drift between workflows and documentation."""
from __future__ import annotations

import re

ACTION_USE_RE = re.compile(
    r"^\s*-?\s*uses:\s*(?P<owner_repo>[\w.\-]+/[\w.\-]+)@(?P<ref>v?\d+(?:\.\d+)*)\s*(?:#.*)?$",
    re.MULTILINE | re.IGNORECASE,
)
DOC_ACTION_RE = re.compile(
    r"(?P<owner_repo>[\w.\-]+/[\w.\-]+)@(?P<ref>v?\d+(?:\.\d+)*)",
    re.IGNORECASE,
)


def _version(ref: str) -> str:
    return ref.lower().lstrip("v")


def find_actions_version_drift(
    workflows: dict[str, str],
    docs: dict[str, str] | None = None,
) -> list[dict]:
    """Return actions whose documented versions disagree with workflow pins."""
    if not docs:
        return []

    documented: dict[str, set[str]] = {}
    for content in docs.values():
        for match in DOC_ACTION_RE.finditer(content):
            key = match.group("owner_repo").lower()
            documented.setdefault(key, set()).add(_version(match.group("ref")))

    drifts: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for filename, content in workflows.items():
        for match in ACTION_USE_RE.finditer(content):
            owner_repo = match.group("owner_repo")
            key = owner_repo.lower()
            workflow_ref = match.group("ref")
            doc_versions = documented.get(key)
            if not doc_versions or _version(workflow_ref) in doc_versions:
                continue
            identity = (filename, key, workflow_ref.lower())
            if identity in seen:
                continue
            seen.add(identity)
            mentions = sorted(doc_versions)
            drifts.append({
                "file": filename,
                "owner_repo": owner_repo,
                "workflow_version": workflow_ref,
                "doc_mentions": mentions,
                "detail": f"{owner_repo}@{workflow_ref} in workflows but docs mention {mentions}",
            })
    return drifts
