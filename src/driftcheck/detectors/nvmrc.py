"""NVMRC drift detection: .nvmrc vs package.json engines.node."""
from __future__ import annotations
import re
from pathlib import Path

NVMRC_RE = re.compile(r'^v?(\d+(?:\.\d+)*)', re.MULTILINE)


def parse_nvmrc_version(text: str) -> str | None:
    """Parse .nvmrc file content to extract Node.js version."""
    m = NVMRC_RE.search(text.strip())
    return m.group(1) if m else None


def _extract_version(version_str: str) -> str:
    """Extract clean version from a string that may have prefixes like >=, v, etc."""
    m = re.search(r'(\d+(?:\.\d+)*)', version_str.strip())
    return m.group(1) if m else version_str.strip()


def _versions_differ(v1: str, v2: str) -> bool:
    """Compare two version strings, ignoring patch differences.
    Major-only versions (e.g., "20") match any version with the same major.
    Returns True if major or minor differ.
    """
    parts1 = _extract_version(v1).split(".")
    parts2 = _extract_version(v2).split(".")
    # If one is major-only, only compare major
    if len(parts1) == 1:
        return parts1[0] != parts2[0]
    if len(parts2) == 1:
        return parts1[0] != parts2[0]
    # Both have at least major.minor — compare major and minor
    return parts1[0] != parts2[0] or parts1[1] != parts2[1]


def find_nvmrc_drift(nvmrc_text: str, package_node: str | None, docs: dict[str, str]) -> list[dict]:
    """Detect drift between .nvmrc and package.json engines.node.

    Returns list of {file, doc_version, nvmrc_version, package_version, pos}.
    """
    nvmrc_version = parse_nvmrc_version(nvmrc_text) if nvmrc_text else None
    if not nvmrc_version:
        return []

    drifts = []

    # Check .nvmrc vs package.json engines.node
    if package_node:
        if _versions_differ(nvmrc_version, package_node):
            drifts.append({
                "file": ".nvmrc",
                "doc_version": nvmrc_version,
                "nvmrc_version": nvmrc_version,
                "package_version": package_node,
                "pos": 0,
            })

    # Check .nvmrc vs README mentions
    node_pat = re.compile(r'(?:node\.?js|node)\s*v?(\d+(?:\.\d+)*)', re.I)
    for fname, content in docs.items():
        for m in node_pat.finditer(content):
            doc_version = m.group(1)
            if _versions_differ(nvmrc_version, doc_version):
                drifts.append({
                    "file": fname,
                    "doc_version": doc_version,
                    "nvmrc_version": nvmrc_version,
                    "package_version": package_node,
                    "pos": m.start(),
                })

    return drifts
