"""Count drift detection: README 'N skills' vs actual filesystem count."""
from __future__ import annotations
import re
from pathlib import Path

COUNT_RE = re.compile(r'(?P<count>\d+)\s+skills?\b', re.I)


def find_count_drift(root: Path, docs: dict[str, str]) -> list[dict]:
    """Detect drift where README says 'N skills' but filesystem has M skill dirs.
    Looks for '<N> skills' patterns in docs and compares to count of immediate
    subdirectories under <root>/skills. Returns drifts where doc count != actual.
    One entry per file (first mismatched count per file).

    Precision: skips sub-counts like "32 skills ship a scripts/_common.py"
    (a subset, not the collection total).
    """
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    try:
        actual = sum(1 for p in skills_dir.iterdir() if p.is_dir())
    except Exception:
        return []
    if actual == 0:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in COUNT_RE.finditer(content):
            try:
                doc_count = int(m.group("count"))
            except ValueError:
                continue
            # Skip subset mentions: "32 skills ship/use/with/via" — not total count
            after = content[m.end():m.end()+30].lower()
            if after.lstrip().startswith(("ship ", "use ", "with ", "via ", "for ")):
                continue
            # Also skip if the surrounding sentence is about a subset feature
            # e.g. "32 skills ship a `scripts/_common.py`"
            window = content[max(0, m.start()-20):m.end()+40].lower()
            if "ship a" in window and "scripts" in window:
                continue
            if doc_count != actual:
                drifts.append({"file": fname, "doc_count": str(doc_count), "actual_count": actual, "pos": m.start()})
                break
    return drifts
