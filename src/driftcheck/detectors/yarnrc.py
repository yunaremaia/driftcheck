"""Yarn RC drift detection: .yml Yarn version vs README mentions."""
from __future__ import annotations
import re

# Match Yarn version mentions in README
YARN_VERSION_RE = re.compile(
    r'(?:yarn|yarnpkg)\s*[:=]?\s*(?P<version>\d[\d.]*)',
    re.I,
)


def parse_yarnrc_version(text: str) -> str | None:
    """Return Yarn version from .yarnrc.yml file."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("yarnPath:"):
            # .yarnrc.yml with yarnPath — extract version from path
            path = line.split(":", 1)[1].strip().strip('"').strip("'")
            m = re.search(r"yarn-(\d[\d.]*)\.cjs$", path)
            if m:
                return m.group(1)
        elif line.startswith("yarnVersion:"):
            version = line.split(":", 1)[1].strip().strip('"').strip("'")
            if version:
                return version
    return None


def find_yarnrc_drift(
    yarnrc_content: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between .yml Yarn version and README mentions."""
    if not yarnrc_content:
        return []

    version = parse_yarnrc_version(yarnrc_content)
    if not version:
        return []

    drifts = []
    for doc_fname, doc_content in docs.items():
        for m in YARN_VERSION_RE.finditer(doc_content):
            doc_ver = m.group("version")
            if not _versions_match(doc_ver, version):
                drifts.append({
                    "file": doc_fname,
                    "tool": "yarn",
                    "doc_version": doc_ver,
                    "yarnrc_version": version,
                    "pos": m.start(),
                })

    return drifts


def _versions_match(doc_ver: str, file_ver: str) -> bool:
    """Return True when versions are equivalent (handles '3' vs '3.0')."""
    if doc_ver == file_ver:
        return True
    if file_ver.startswith(doc_ver + "."):
        return True
    if doc_ver.startswith(file_ver + "."):
        return True
    doc_parts = doc_ver.split(".")
    file_parts = file_ver.split(".")
    if len(doc_parts) >= 2 and len(file_parts) >= 2:
        return doc_parts[0] == file_parts[0] and doc_parts[1] == file_parts[1]
    return False
