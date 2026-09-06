"""Node.js drift detection: package.json engines.node vs README mentions."""
from __future__ import annotations
import re
import json

NODE_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version)\s+Node(?:\.js)?\s+(?P<ver>[0-9]+(?:\.[0-9]+)?)',
    re.I
)
ENGINES_RE = re.compile(r'"node"\s*:\s*"(?P<ver>[^"]+)"')


def parse_node_version_from_package(text: str) -> str | None:
    try:
        data = json.loads(text)
        eng = data.get("engines", {}).get("node", "")
        if not eng:
            return None
        m = re.search(r"[0-9]+", eng)
        return m.group(0) if m else None
    except Exception:
        return None


def find_node_drift(package_text: str, docs: dict[str, str]) -> list[dict]:
    pv = parse_node_version_from_package(package_text)
    if not pv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in NODE_RE.finditer(content):
            dv = m.group("ver")
            # Check if this match is on a numbered list line (1., 2., etc.) - common in TOC
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue  # Skip TOC/list numbering
            if dv != pv:
                drifts.append({"file": fname, "doc_version": dv, "package_version": pv, "pos": m.start()})
                break
    return drifts
