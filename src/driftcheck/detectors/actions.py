"""GitHub Actions drift detection: deprecated Node 20 runtime and outdated action versions."""
from __future__ import annotations
import re
from pathlib import Path

ACTIONS_NODE24_FIX = {
    "actions/checkout": {"deprecated": "v4", "fixed": "v5"},
    "actions/setup-node": {"deprecated": "v4", "fixed": "v5"},
    "actions/configure-pages": {"deprecated": "v5", "fixed": "v6"},
    "actions/deploy-pages": {"deprecated": "v4", "fixed": "v5"},
    "pnpm/action-setup": {"deprecated": "v4", "fixed": "v5"},
}
ACTIONS_RE = re.compile(r'uses:\s*(?P<action>[A-Za-z0-9_.\-\/]+)\s*@\s*(?P<ver>v\d+(?:\.\d+)*)', re.I)

# Known latest versions for popular actions (update periodically)
# Last updated: 2026-09-09
GH_ACTIONS_LATEST = {
    "actions/checkout": "v7",
    "actions/setup-node": "v7",
    "actions/setup-python": "v7",
    "actions/setup-java": "v6",
    "actions/setup-go": "v7",
    "actions/cache": "v6",
    "actions/upload-artifact": "v7",
    "actions/download-artifact": "v8",
    "pnpm/action-setup": "v5",
    "actions/configure-pages": "v6",
    "actions/deploy-pages": "v6",
    "actions/stale": "v11",
    "actions/labeler": "v7",
    "actions/dependency-review-action": "v5",
    "github/codeql-action/init": "v4",
    "github/codeql-action/analyze": "v4",
    "codecov/codecov-action": "v7",
    "dorny/test-reporter": "v2",
}

GH_ACTIONS_RE = re.compile(r'uses:\s*(?P<action>[A-Za-z0-9_.\-\/]+)\s*@(?P<ver>v\d+(?:\.\d+)*)', re.I)


def find_actions_node_drift(root: Path) -> list[dict]:
    """Detect GitHub Actions still pinned to deprecated Node 20 runtime versions.
    Scans .github/workflows/*.yml/.yaml for known actions where the pinned
    major version still uses node20 and a node24 fixed version exists.
    Returns list of {file, action, current, suggested, pos}.
    """
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    drifts = []
    for wf in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        try:
            text = wf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(wf.relative_to(root))
        for m in ACTIONS_RE.finditer(text):
            action = m.group("action")
            ver = m.group("ver").lower()
            # normalize v4.1.0 -> v4
            major = ver.split(".")[0]
            fix = ACTIONS_NODE24_FIX.get(action)
            if not fix:
                continue
            dep_major = fix["deprecated"].lower()
            if major == dep_major:
                drifts.append({"file": rel, "action": action, "current": ver, "suggested": fix["fixed"], "pos": m.start()})
    return drifts


def find_gh_actions_version_drift(root: Path) -> list[dict]:
    """Detect outdated GitHub Actions versions in .github/workflows/*.yml/.yaml.
    Returns list of {file, action, current, suggested, pos}.
    """
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    drifts = []
    for wf in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        try:
            text = wf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(wf.relative_to(root))
        for m in GH_ACTIONS_RE.finditer(text):
            action = m.group("action")
            ver = m.group("ver").lower()
            latest = GH_ACTIONS_LATEST.get(action)
            if not latest:
                continue
            # Compare major versions only
            ver_major = ver.split(".")[0]
            latest_major = latest.split(".")[0]
            if ver_major != latest_major:
                drifts.append({
                    "file": rel,
                    "action": action,
                    "current": ver,
                    "suggested": latest,
                    "pos": m.start(),
                })
    return drifts
