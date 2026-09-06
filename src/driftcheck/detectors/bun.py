"""Bun drift detection: package.json engines.bun vs README mentions."""
from __future__ import annotations
import re
import json

BUN_ENGINES_RE = re.compile(r'"bun"\s*:\s*"(?P<ver>[^\"]+)"')
BUN_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)\s+Bun\s+(?P<ver>\d+(?:\.\d+)?)|(?<!\w)Bun\s+(?P<ver2>\d+(?:\.\d+)?)(?=\s|$|,|\.|;)',
    re.I
)


def parse_bun_version_from_package(text: str) -> str | None:
    """Parse Bun version from package.json engines.bun. Returns major.minor (e.g., '1.0')."""
    try:
        data = json.loads(text)
        bun_ver = data.get("engines", {}).get("bun", "")
        if not bun_ver:
            return None
        # Handle ranges like ">=1.0", "^1.0", "~1.0"
        bun_ver = re.sub(r'[\^~>=<]+', '', bun_ver).strip()
        parts = bun_ver.split('.')
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return bun_ver
    except Exception:
        return None


def find_bun_drift(package_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Bun version drift between package.json engines.bun and README mentions.

    Returns list of {file, doc_version, package_version, pos}.
    Only flags when the doc's Bun major.minor doesn't match package.json.
    """
    if not package_text:
        return []
    bv = parse_bun_version_from_package(package_text)
    if not bv:
        return []
    bv_major_minor = ".".join(bv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in BUN_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != bv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "package_version": bv,
                    "pos": m.start(),
                })
                break
    return drifts
