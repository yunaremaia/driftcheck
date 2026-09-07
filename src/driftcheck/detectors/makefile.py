from __future__ import annotations
import re

MAKEFILE_VERSION_VAR_RE = re.compile(
    r'^\s*(?P<var>(?:GCC|CC|MAKE|CMAKE|RUST|GO|PYTHON|NODE|JAVA|PHP|RUBY|CXX)_VERSION)\s*[:?]?=\s*(?P<ver>\S+)',
    re.M,
)
MAKEFILE_TOOL_ASSIGN_RE = re.compile(
    r'^\s*(?P<var>(?:GCC|CC|CXX|CMAKE|MAKE|RUSTC|GO|RUBY|PHP|JAVA|PYTHON|NODE))\s*[:?]?=\s*(?P<ver>\S+)',
    re.M,
)


def parse_makefile_versions(text: str) -> dict[str, str]:
    """Parse tool versions from Makefile variable assignments."""
    versions = {}
    for m in MAKEFILE_VERSION_VAR_RE.finditer(text):
        versions[m.group('var')] = m.group('ver')
    for m in MAKEFILE_TOOL_ASSIGN_RE.finditer(text):
        var = m.group('var')
        ver = m.group('ver')
        if re.match(r'^\d+\.\d+', ver):
            versions.setdefault(var, ver)
    return versions


def find_makefile_drift(makefile_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between Makefile version variables and README mentions."""
    versions = parse_makefile_versions(makefile_text)
    if not versions:
        return []
    drifts = []
    for fname, content in docs.items():
        for var, ver in versions.items():
            tool = var.replace('_VERSION', '').replace('_version', '')
            major_minor = '.'.join(ver.split('.')[:2])
            pattern = re.compile(
                rf'\b{re.escape(tool)}\s+(?P<docver>\d+(?:\.\d+){{0,2}})\b',
                re.I,
            )
            for m in pattern.finditer(content):
                doc_ver = m.group('docver')
                doc_major_minor = '.'.join(doc_ver.split('.')[:2])
                if doc_major_minor != major_minor:
                    drifts.append({
                        'file': fname,
                        'tool': tool,
                        'doc_version': doc_ver,
                        'makefile_version': ver,
                        'pos': m.start(),
                    })
    return drifts
