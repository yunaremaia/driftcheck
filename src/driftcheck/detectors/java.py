"""Java/Gradle drift detection: build.gradle sourceCompatibility vs README."""
from __future__ import annotations
import re

GRADLE_JAVA_RE = re.compile(r'sourceCompatibility\s*=\s*["\']?(?P<ver>\d+(?:\.\d+)?)["\']?|JavaVersion\.VERSION_(?P<ver2>_\d+|(?:\d+))', re.I)
GRADLE_KOTLIN_RE = re.compile(r'jvmTarget\s*=\s*["\']?(?P<ver>\d+(?:\.\d+)?)["\']?', re.I)
JAVA_DOC_RE = re.compile(r'(?:Java|JDK|JRE|JVM)\s+(?P<ver>\d+(?:\.\d+)?)', re.I)


def parse_gradle_java_version(text: str) -> str | None:
    """Parse Java version from build.gradle sourceCompatibility or jvmTarget."""
    m = GRADLE_JAVA_RE.search(text)
    if m:
        v = m.group("ver") or m.group("ver2")
        if v:
            return v.replace("_", "")
    m = GRADLE_KOTLIN_RE.search(text)
    if m:
        return m.group("ver")
    return None


def find_java_drift(gradle_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between build.gradle Java version and README mentions."""
    jv = parse_gradle_java_version(gradle_text)
    if not jv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in JAVA_DOC_RE.finditer(content):
            dv = m.group("ver")
            # Normalize: "17.0.1" -> "17" for comparison with sourceCompatibility
            dv_major = dv.split(".")[0]
            jv_major = jv.split(".")[0]
            if dv_major != jv_major:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "gradle_version": jv,
                    "pos": m.start(),
                })
                break
    return drifts
