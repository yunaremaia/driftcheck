"""Ruby drift detection: Gemfile ruby version vs README mentions."""
from __future__ import annotations
import re

GEMFILE_RUBY_RE = re.compile(r'^\s*ruby\s+["\'](?P<ver>\d+\.\d+(?:\.\d+)?)["\']', re.MULTILINE)
RUBY_DOC_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version|with|needs)\s+Ruby\s+(?P<ver>\d+\.\d+(?:\.\d+)?)|(?<!\w)Ruby\s+(?P<ver2>\d+\.\d+(?:\.\d+)?)(?=\s|$|,|\.|;)',
    re.I
)


def parse_gemfile_ruby_version(text: str) -> str | None:
    """Parse ruby version from Gemfile. Returns major.minor (e.g., '3.2')."""
    m = GEMFILE_RUBY_RE.search(text)
    return m.group("ver") if m else None


def find_ruby_drift(gemfile_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Ruby version drift between Gemfile and README mentions.

    Returns list of {file, doc_version, gemfile_version, pos}.
    Only flags when the doc's Ruby major.minor doesn't match Gemfile.
    """
    if not gemfile_text:
        return []
    gv = parse_gemfile_ruby_version(gemfile_text)
    if not gv:
        return []
    gv_major_minor = ".".join(gv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in RUBY_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != gv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "gemfile_version": gv,
                    "pos": m.start(),
                })
                break
    return drifts
