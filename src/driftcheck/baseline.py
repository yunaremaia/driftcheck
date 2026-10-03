"""Baseline mode for driftcheck.

Enables incremental drift detection by accepting the current state as "known good"
and only reporting NEW drifts that appear after the baseline is set.

File format: .driftcheck-baseline.json in repo root.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .detector import scan_repo

BASELINE_FILENAME = ".driftcheck-baseline.json"
BASELINE_SCHEMA_VERSION = 1


def _get_commit_sha(root: Path) -> str:
    """Get current git commit SHA, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "unknown"


def _make_drift_key(detector: str, drift: dict) -> tuple[str, str, str]:
    """Create a dedup key for a drift entry.

    Key is (detector, file, type) where type is derived from the drift's
    content to distinguish different drift types on the same file.
    """
    file = drift.get("file", "")
    # Derive a type key from the drift's distinguishing features
    if "doc_version" in drift:
        type_key = f"doc={drift['doc_version']}"
    elif "detail" in drift:
        type_key = f"detail={drift['detail'][:80]}"
    elif "runner" in drift:
        type_key = f"runner={drift['runner']}"
    elif "action" in drift:
        type_key = f"action={drift['action']}@{drift.get('current', '')}"
    elif "image" in drift:
        type_key = f"image={drift['image']}"
    else:
        # Fallback: use sorted keys to create a stable fingerprint
        type_key = str(sorted(drift.items()))
    return (detector, file, type_key)


def _result_to_baseline_entries(result: dict) -> list[dict]:
    """Convert scan_repo result to a list of baseline drift entries."""
    entries = []
    for key, drifts in result.items():
        if not isinstance(drifts, list):
            continue
        if key in ("_skipped_symlinks",):
            continue
        for drift in drifts:
            if not isinstance(drift, dict):
                continue
            detector, file, type_key = _make_drift_key(key, drift)
            entries.append({
                "detector": key,
                "file": file,
                "type": type_key,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                # Store original drift data for reference
                "drift": drift,
            })
    return entries


def create_baseline(root: Path, result: dict | None = None) -> dict:
    """Create a baseline from the current repository state.

    Args:
        root: repo root path
        result: pre-computed scan result (if None, will scan)

    Returns:
        The baseline dict that was written
    """
    if result is None:
        result = scan_repo(root)

    commit_sha = _get_commit_sha(root)
    entries = _result_to_baseline_entries(result)

    baseline = {
        "version": BASELINE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "total_entries": len(entries),
        "drifts": entries,
    }

    baseline_path = root / BASELINE_FILENAME
    baseline_path.write_text(
        json.dumps(baseline, indent=2, default=str),
        encoding="utf-8",
    )

    # Add to .gitignore if not already there
    _add_to_gitignore(root)

    return baseline


def load_baseline(root: Path) -> dict | None:
    """Load baseline from disk.

    Returns:
        The baseline dict, or None if no baseline exists or schema mismatch.
    """
    baseline_path = root / BASELINE_FILENAME
    if not baseline_path.exists():
        return None

    try:
        text = baseline_path.read_text(encoding="utf-8")
        baseline = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None

    if baseline.get("version") != BASELINE_SCHEMA_VERSION:
        return None

    return baseline


def update_baseline(root: Path, result: dict | None = None) -> dict:
    """Update the baseline to the current state.

    Preserves first_seen timestamps for drifts that existed before.
    """
    old_baseline = load_baseline(root)
    old_first_seen: dict[tuple, str] = {}

    if old_baseline:
        for entry in old_baseline.get("drifts", []):
            key = (entry.get("detector", ""), entry.get("file", ""), entry.get("type", ""))
            old_first_seen[key] = entry.get("first_seen", "")

    if result is None:
        result = scan_repo(root)

    commit_sha = _get_commit_sha(root)
    entries = _result_to_baseline_entries(result)

    # Preserve first_seen for drifts that existed before
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        key = (entry["detector"], entry["file"], entry["type"])
        if key in old_first_seen:
            entry["first_seen"] = old_first_seen[key]
        else:
            entry["first_seen"] = now

    baseline = {
        "version": BASELINE_SCHEMA_VERSION,
        "created_at": old_baseline.get("created_at", now) if old_baseline else now,
        "updated_at": now,
        "commit_sha": commit_sha,
        "total_entries": len(entries),
        "drifts": entries,
    }

    baseline_path = root / BASELINE_FILENAME
    baseline_path.write_text(
        json.dumps(baseline, indent=2, default=str),
        encoding="utf-8",
    )

    return baseline


def reset_baseline(root: Path) -> bool:
    """Remove the baseline file.

    Returns:
        True if a baseline was removed, False if none existed.
    """
    baseline_path = root / BASELINE_FILENAME
    if baseline_path.exists():
        baseline_path.unlink()
        return True
    return False


def compare_against_baseline(
    root: Path, result: dict, baseline: dict | None = None
) -> dict:
    """Compare current scan results against the baseline.

    Args:
        root: repo root path
        result: current scan_repo() result
        baseline: pre-loaded baseline (if None, will load from disk)

    Returns:
        Dict with:
            - new_drifts: drifts not in baseline (failures)
            - pre_existing_drifts: drifts in baseline (warnings)
            - baseline_info: metadata about the baseline
    """
    if baseline is None:
        baseline = load_baseline(root)

    if baseline is None:
        # No baseline: all drifts are "new"
        all_drifts = {}
        for key, drifts in result.items():
            if isinstance(drifts, list) and key != "_skipped_symlinks":
                all_drifts[key] = drifts
        return {
            "new_drifts": all_drifts,
            "pre_existing_drifts": {},
            "baseline_info": None,
        }

    # Build set of baseline drift keys
    baseline_keys: set[tuple] = set()
    for entry in baseline.get("drifts", []):
        key = (entry.get("detector", ""), entry.get("file", ""), entry.get("type", ""))
        baseline_keys.add(key)

    new_drifts: dict[str, list] = {}
    pre_existing_drifts: dict[str, list] = {}

    for key, drifts in result.items():
        if not isinstance(drifts, list) or key == "_skipped_symlinks":
            continue
        for drift in drifts:
            if not isinstance(drift, dict):
                continue
            _, _, type_key = _make_drift_key(key, drift)
            drift_key = (key, drift.get("file", ""), type_key)
            if drift_key in baseline_keys:
                pre_existing_drifts.setdefault(key, []).append(drift)
            else:
                new_drifts.setdefault(key, []).append(drift)

    return {
        "new_drifts": new_drifts,
        "pre_existing_drifts": pre_existing_drifts,
        "baseline_info": {
            "created_at": baseline.get("created_at"),
            "updated_at": baseline.get("updated_at"),
            "commit_sha": baseline.get("commit_sha"),
            "total_entries": baseline.get("total_entries"),
        },
    }


def show_baseline(root: Path) -> str:
    """Return a human-readable summary of the baseline."""
    baseline = load_baseline(root)
    if baseline is None:
        return "No baseline found. Run 'driftcheck --baseline' to create one."

    lines = [
        f"Baseline created: {baseline.get('created_at', 'unknown')}",
        f"Last updated:    {baseline.get('updated_at', 'unknown')}",
        f"Commit SHA:      {baseline.get('commit_sha', 'unknown')}",
        f"Total drifts:    {baseline.get('total_entries', 0)}",
        "",
    ]

    # Group by detector
    by_detector: dict[str, list] = {}
    for entry in baseline.get("drifts", []):
        detector = entry.get("detector", "unknown")
        by_detector.setdefault(detector, []).append(entry)

    for detector, entries in sorted(by_detector.items()):
        lines.append(f"  {detector}: {len(entries)} drift(s)")
        for e in entries[:3]:  # Show first 3 per detector
            lines.append(f"    - {e.get('file', '?')}: {e.get('type', '')[:60]}")
        if len(entries) > 3:
            lines.append(f"    ... and {len(entries) - 3} more")

    return "\n".join(lines)


def _add_to_gitignore(root: Path) -> None:
    """Add the baseline file to .gitignore if not already tracked."""
    gitignore_path = root / ".gitignore"
    entry = BASELINE_FILENAME

    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if entry in content:
            return
        # Append with newline if file doesn't end with one
        if content and not content.endswith("\n"):
            content += "\n"
        content += entry + "\n"
        gitignore_path.write_text(content, encoding="utf-8")
    else:
        gitignore_path.write_text(entry + "\n", encoding="utf-8")
