"""Dart/Flutter drift detection: pubspec.yaml environment.sdk vs README mentions."""
from __future__ import annotations
import re

# Match pubspec.yaml SDK constraint like `sdk: ">=3.0.0 <4.0.0"` or `sdk: ^3.0.0`
DART_SDK_RE = re.compile(r'environment:\s*\n\s*sdk:\s*["\']?(?P<constraint>[^"\']+)["\']?', re.I)
# Simpler single-line fallback
DART_SDK_INLINE_RE = re.compile(r'sdk:\s*["\']?(?P<constraint>[^"\']+)["\']?', re.I)
# Match README mentions like "Dart 3.0", "Dart SDK 3.2"
# Note: intentionally excludes "Flutter" — Flutter release versions are
# independent of the Dart SDK version (e.g., Flutter 3.10 ships with Dart 3.2).
DART_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)?\s*Dart\s+(?:SDK\s+)?(?P<ver>\d+(?:\.\d+){0,2})',
    re.I
)


def _parse_constraint(constraint: str) -> str | None:
    """Extract base version from a Dart SDK constraint string.

    Handles: ">=3.0.0 <4.0.0", "^3.0.0", ">=2.17.0", "3.0.0"
    """
    # Match the first numeric version in the constraint
    m = re.search(r'(\d+(?:\.\d+){0,2})', constraint.strip())
    return m.group(1) if m else None


def parse_dart_sdk_version(pubspec_text: str) -> str | None:
    """Parse Dart SDK version from pubspec.yaml.

    Returns major.minor (e.g., '3.2') extracted from the `environment.sdk` constraint.
    """
    m = DART_SDK_RE.search(pubspec_text) or DART_SDK_INLINE_RE.search(pubspec_text)
    if not m:
        return None
    return _parse_constraint(m.group("constraint"))


def find_dart_drift(pubspec_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between pubspec.yaml SDK constraint and README mentions.

    Returns list of {file, doc_version, pubspec_version, pos}.
    Only flags when the doc's Dart major.minor doesn't match pubspec.
    """
    if not pubspec_text:
        return []
    sv = parse_dart_sdk_version(pubspec_text)
    if not sv:
        return []
    sv_parts = sv.split(".")
    # Normalize to major.minor
    sv_normalized = ".".join(sv_parts[:2]) if len(sv_parts) >= 2 else sv

    drifts = []
    for fname, content in docs.items():
        for m in DART_DOC_RE.finditer(content):
            dv = m.group("ver")
            # Skip TOC/list numbering
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_parts = dv.split(".")
            dv_normalized = ".".join(dv_parts[:2]) if len(dv_parts) >= 2 else dv
            if dv_normalized != sv_normalized:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "pubspec_version": sv,
                    "pos": m.start(),
                })
                break
    return drifts
