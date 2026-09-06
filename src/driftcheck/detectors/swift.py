"""Swift Package Manager drift detection: Package.swift version pins vs README."""
from __future__ import annotations
import re

# Match Package.swift version pins like `.package(url: ..., from: "5.0.0")` or `.exact("1.2.3")`
SPM_VERSION_RE = re.compile(r'\.(?:package|executableTarget|target)\([^)]*(?:from:|exact:|version:)\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"')
# Match README mentions of Swift version
SWIFT_DOC_RE = re.compile(r'(?:Swift|swift)\s+(?P<ver>[0-9]+(?:\.[0-9]+){0,2})', re.I)


def parse_swift_version_from_package(text: str) -> str | None:
    """Parse Swift version from Package.swift (from platform or dependency pins)."""
    # First try to find swift-tools-version at top
    m = re.search(r'swift-tools-version:\s*(?P<ver>[0-9]+(?:\.[0-9]+){0,2})', text)
    if m:
        return m.group("ver")
    # Fall back to dependency version pins
    m = SPM_VERSION_RE.search(text)
    return m.group("ver") if m else None


def find_swift_drift(package_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between Package.swift version pins and README mentions."""
    pv = parse_swift_version_from_package(package_text)
    if not pv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in SWIFT_DOC_RE.finditer(content):
            dv = m.group("ver")
            # Compare major.minor (ignore patch)
            pv_parts = pv.split(".")
            dv_parts = dv.split(".")
            if pv_parts[:2] != dv_parts[:2]:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "package_version": pv,
                    "pos": m.start(),
                })
                break  # one per file
    return drifts
