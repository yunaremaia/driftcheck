"""Kotlin drift detection: build.gradle.kts kotlin plugin version vs README."""
from __future__ import annotations
import re

# Match kotlin plugin version in build.gradle.kts
# kotlin("jvm") version "1.9.0"
# kotlin("plugin.spring") version "1.9.0"
# id("org.jetbrains.kotlin.jvm") version "1.9.0"
KOTLIN_PLUGIN_RE = re.compile(
    r'(?:kotlin\s*\(\s*["\'](?:jvm|plugin\.(?:spring|serialization|allopen|kapt))["\']\s*\)|id\s*\(\s*["\']org\.jetbrains\.kotlin\.(?:jvm|android|plugin\.(?:spring|serialization))["\']\s*\))\s+version\s+["\']([\d.]+)["\']',
    re.I,
)
# Fallback: any kotlin version reference
KOTLIN_VERSION_RE = re.compile(
    r'kotlin\s*\(\s*["\'][^"\']+["\']\s*\)\s+version\s+["\']([\d.]+)["\']',
    re.I,
)
# Match Kotlin mentions in docs
KOTLIN_DOC_RE = re.compile(
    r'(?:kotlin|require[s]?\s+kotlin)\s*v?(\d+\.\d+(?:\.\d+)?)',
    re.I,
)


def parse_kotlin_version(text: str) -> str | None:
    """Parse Kotlin version from build.gradle.kts.

    Expects: kotlin("jvm") version "1.9.0"
    Returns: "1.9.0"
    """
    m = KOTLIN_PLUGIN_RE.search(text)
    if m:
        return m.group(1)
    m = KOTLIN_VERSION_RE.search(text)
    return m.group(1) if m else None


def find_kotlin_drift(gradle_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Kotlin version drift between build.gradle.kts and README.

    Args:
        gradle_text: content of build.gradle.kts
        docs: {relative_path: content} of README/CONTRIBUTING files

    Returns list of {file, doc_version, gradle_version, pos}.
    """
    gradle_ver = parse_kotlin_version(gradle_text)
    if not gradle_ver:
        return []

    drifts = []
    for rel_path, text in docs.items():
        for m in KOTLIN_DOC_RE.finditer(text):
            doc_ver = m.group(1)
            doc_parts = doc_ver.split(".")
            gradle_parts = gradle_ver.split(".")
            # Major.minor comparison (ignore patch)
            if doc_parts[:2] != gradle_parts[:2]:
                drifts.append({
                    "file": rel_path,
                    "doc_version": doc_ver,
                    "gradle_version": gradle_ver,
                    "pos": m.start(),
                })
                break  # one drift per file
    return drifts
