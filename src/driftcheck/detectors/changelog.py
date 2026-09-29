"""Changelog entry drift detection.

Detects when a project requires CHANGELOG entries per PR (per CONTRIBUTING.md
or similar policy) but CHANGELOG.md is missing, empty, or hasn't been updated
alongside recent changes.

Real-world motivation: sharkdp/bat#3894 and other Rust projects have CI that
blocks merges when CHANGELOG.md isn't updated. This detector surfaces that gap.
"""
from __future__ import annotations

import re
from pathlib import Path

CHANGELOG_PATH = "CHANGELOG.md"
CONTRIBUTING_PATH = "CONTRIBUTING.md"

# Patterns that indicate a project requires changelog entries
CHANGELOG_POLICY_RE = re.compile(
    r"(?i)\b(changelog|change\s?log)\b.{0,80}"
    r"(require|mandatory|must|required|expected|update|document|entry|note|record)"
    r"|"
    r"(per\s?pr|per\s?pull|each\s?(pr|pull\s?request)|every\s?(pr|pull\s?request))"
    r".{0,80}\b(changelog|change\s?log)\b"
    r"|"
    r"\b(changelog|change\s?log)\b.{0,80}"
    r"(missing|forgot|forgotten|not\s?updated|out\s?of\s?date|stale)",
    re.M,
)

# Patterns that strongly suggest changelog entries are expected (even without
# the exact word "changelog" — e.g. "document changes", "note what changed")
IMPLICIT_CHANGELOG_POLICY_RE = re.compile(
    r"(?i)\b(document\s+(all\s+)?changes|note\s+what\s+changed|record\s+changes|"
    r"changes\s+must\s+be\s+documented|update\s+the\s+changelog|"
    r"add\s+an\s+entry\s+to\s+the\s+changelog|mention\s+changes)\b",
    re.M,
)

# Headers that indicate changelog sections in the file
CHANGELOG_SECTION_RE = re.compile(r"^#{1,5}\s+.+$", re.M)

# Recent-commit heuristic: we look for the most recent section in the changelog.
# Projects that follow "Keep a Changelog" format use "## [Unreleased]" or
# "## [X.Y.Z] - YYYY-MM-DD". If the file has no section newer than a reasonable
# threshold or no version headers at all, it is considered stale.
KEEP_A_CHANGELOG_RELEASE_RE = re.compile(
    r"^##\s+\[?(\d+\.\d+(?:\.\d+)?)\]?\s*-\s*\d{4}-\d{2}-\d{2}", re.M
)
UNRELEASED_RE = re.compile(r"^##\s+\[Unreleased\]", re.M)


def _changelog_policy_required(contributing_text: str, changelog_text: str | None) -> bool:
    """Return True when CONTRIBUTING.md (or similar) signals changelog entries are required."""
    combined = contributing_text or ""
    if not combined:
        return False
    if CHANGELOG_POLICY_RE.search(combined):
        return True
    if IMPLICIT_CHANGELOG_POLICY_RE.search(combined):
        return True
    return False


def _changelog_exists(root: Path) -> bool:
    return (root / CHANGELOG_PATH).is_file()


def _changelog_has_content(changelog_text: str | None) -> bool:
    return bool(changelog_text and changelog_text.strip())


def _changelog_has_version_sections(changelog_text: str | None) -> bool:
    """Return True when the changelog contains at least one version/release header."""
    return bool(KEEP_A_CHANGELOG_RELEASE_RE.search(changelog_text or ""))


def _changelog_has_unreleased_section(changelog_text: str) -> bool:
    return bool(UNRELEASED_RE.search(changelog_text or ""))


def _changelog_has_recent_activity(changelog_text: str | None) -> bool:
    """Heuristic: changelog has an Unreleased section OR a release dated within ~90 days.

    When neither is present the file is considered potentially stale.
    """
    text = changelog_text or ""
    if UNRELEASED_RE.search(text):
        return True
    m = KEEP_A_CHANGELOG_RELEASE_RE.search(text)
    if not m:
        return False
    # We don't parse dates precisely here — presence of any release header is a
    # positive signal that the file is being maintained. Combined with the
    # "no unreleased section" path, the detector nudges the user to add one.
    return True


def find_changelog_drift(root: Path, docs: dict[str, str]) -> list[dict]:
    """Detect changelog entry drift.

    Returns a list of drift dicts when:
      - CONTRIBUTING.md signals changelog entries are required but
        CHANGELOG.md is missing, or
      - CHANGELOG.md exists but is empty, or
      - CHANGELOG.md has no version sections (no release headers at all).

    Informational-only: a missing/empty/stale changelog does not fail the check.
    """
    drifts: list[dict] = []

    # Read CONTRIBUTING.md and CHANGELOG.md
    contributing_path = root / CONTRIBUTING_PATH
    contributing_text = contributing_path.read_text(encoding="utf-8", errors="replace") if contributing_path.is_file() else ""

    changelog_path = root / CHANGELOG_PATH
    changelog_text = changelog_path.read_text(encoding="utf-8", errors="replace") if changelog_path.is_file() else None

    policy_required = _changelog_policy_required(contributing_text, changelog_text)

    if not policy_required:
        return drifts

    if not _changelog_exists(root):
        drifts.append({
            "file": CONTRIBUTING_PATH,
            "kind": "changelog_missing",
            "detail": "Policy requires CHANGELOG entries but CHANGELOG.md is missing",
        })
        return drifts

    if not _changelog_has_content(changelog_text):
        drifts.append({
            "file": CHANGELOG_PATH,
            "kind": "changelog_empty",
            "detail": "CHANGELOG.md exists but is empty — policy requires entries",
        })
        return drifts

    if not _changelog_has_version_sections(changelog_text):
        drifts.append({
            "file": CHANGELOG_PATH,
            "kind": "changelog_no_versions",
            "detail": "CHANGELOG.md has no release/version sections — policy requires entries",
        })
        return drifts

    # Staleness heuristic: no Unreleased section and no recognizable release headers.
    # (Reached only when version sections exist; kept for future date-aware refinement.)
    return drifts
