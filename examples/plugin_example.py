"""Example driftcheck plugin — detect mentions of outdated project name in README.

Copy this file to .driftcheck_plugins/ in your repo root to activate.
driftcheck will load it automatically and run it during scan.
"""
from __future__ import annotations
import re
from pathlib import Path

# Configure: set your project's current name and previous names to watch for
CURRENT_NAME = "DriftCheck"
OLD_NAMES = ["Driftchecker", "driftchecker", "drift-check"]


def register() -> dict:
    """Register this plugin's detectors with driftcheck."""
    return {"project_name": find_old_name_mentions}


def find_old_name_mentions(root: Path, docs: dict[str, str]) -> list[dict]:
    """Detect README/docs that reference the old project name.

    Returns list of {file, doc_version, detail} — driftcheck's standard drift format.
    """
    drifts = []
    for old_name in OLD_NAMES:
        pattern = re.compile(re.escape(old_name))
        for fname, content in docs.items():
            for m in pattern.finditer(content):
                line_num = content[:m.start()].count('\n') + 1
                drifts.append({
                    "file": fname,
                    "doc_version": old_name,
                    "detail": f"line {line_num}: '{old_name}' should be '{CURRENT_NAME}'",
                    "pos": m.start(),
                })
    return drifts
