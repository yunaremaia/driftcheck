"""Go drift detection: go.mod version vs README mentions."""
from __future__ import annotations
import re

GO_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version|build|test|with|requires)\s+Go\s+(?P<ver>[0-9]+\.[0-9]+)|(?<=\s)Go\s+(?P<ver2>[0-9]+\.[0-9]+)(?=\s|$|,|\.|;)(?!\s+(?:and|or)\s+(?:later|earlier))',
    re.I
)
GO_MOD_RE = re.compile(r'^\s*go\s+(?P<ver>[0-9]+\.[0-9]+)', re.MULTILINE)


def parse_go_version_from_gomod(text: str) -> str | None:
    m = GO_MOD_RE.search(text)
    return m.group("ver") if m else None


def find_go_drift(gomod_text: str, docs: dict[str, str]) -> list[dict]:
    gv = parse_go_version_from_gomod(gomod_text)
    if not gv:
        return []
    # Normalize go.mod version to major.minor
    gv_minor = ".".join(gv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in GO_RE.finditer(content):
            dv = m.group("ver")
            # Check if this match is on a numbered list line
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue  # Skip TOC/list numbering
            if dv != gv_minor:
                drifts.append({"file": fname, "doc_version": dv, "gomod_version": gv, "pos": m.start()})
                break
    return drifts
