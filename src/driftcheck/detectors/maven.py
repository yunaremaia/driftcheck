"""Maven drift detection: pom.xml version vs README."""
from __future__ import annotations
import re

MAVEN_VER_RE = re.compile(r'<(?:java\.version|maven\.compiler\.source|maven\.compiler\.target|release)>(?P<ver>\d+(?:\.\d+)?)</')
MAVEN_DOC_RE = re.compile(r'(?:Java|JDK|JRE|requires)\s+(?P<ver>\d+(?:\.\d+)?)', re.I)


def parse_maven_java_version(text: str) -> str | None:
    """Parse Java version from pom.xml java.version or maven.compiler.source."""
    m = MAVEN_VER_RE.search(text)
    return m.group("ver") if m else None


def find_maven_drift(pom_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between pom.xml Java version and README mentions."""
    mv = parse_maven_java_version(pom_text)
    if not mv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in MAVEN_DOC_RE.finditer(content):
            dv = m.group("ver")
            dv_major = dv.split(".")[0]
            mv_major = mv.split(".")[0]
            if dv_major != mv_major:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "maven_version": mv,
                    "pos": m.start(),
                })
                break
    return drifts
