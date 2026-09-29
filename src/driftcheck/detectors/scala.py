"""Scala/SBT drift: scalaVersion and libraryDependencies vs README mentions."""
from __future__ import annotations

import re

_SCALA_RE = re.compile(r'scalaVersion\s*:=\s*"([^"]+)"')
_DEP_RE = re.compile(
    r'%%?\s*"(?P<name>[A-Za-z0-9_.\-]+)"\s*%\s*"(?P<ver>[^"]+)"'
)
_DOC_SCALA_RE = re.compile(r"\bScala\s+v?(?P<ver>\d+\.\d+(?:\.\d+)?)\b", re.I)
_DOC_DEP_RE = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9_.\-]+)\s+v?(?P<ver>\d+\.\d+(?:\.\d+)?)\b"
)


def _major_minor(version: str) -> str:
    parts = version.split(".")
    return parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[1]}"


def parse_sbt(text: str) -> tuple[str | None, dict[str, str]]:
    """Return (scalaVersion, {artifact: version}) from an SBT build definition."""
    scala = None
    match = _SCALA_RE.search(text)
    if match:
        scala = match.group(1)
    deps: dict[str, str] = {}
    for dep in _DEP_RE.finditer(text):
        deps.setdefault(dep.group("name"), dep.group("ver"))
    return scala, deps


def find_scala_drift(sbt_text: str, docs: dict[str, str]) -> list[dict]:
    """Flag README Scala or artifact versions that disagree with build.sbt on major.minor."""
    scala, deps = parse_sbt(sbt_text)
    if not scala and not deps:
        return []
    drifts: list[dict] = []
    for fname, content in docs.items():
        if scala:
            for match in _DOC_SCALA_RE.finditer(content):
                doc_ver = match.group("ver")
                if _major_minor(doc_ver) == _major_minor(scala):
                    continue
                drifts.append({
                    "file": fname,
                    "tool": "Scala",
                    "doc_version": doc_ver,
                    "sbt_version": scala,
                    "detail": f"Scala {doc_ver} in {fname} should be {scala} (build.sbt)",
                    "pos": match.start(),
                })
                break
        seen: set[str] = set()
        for match in _DOC_DEP_RE.finditer(content):
            name = match.group("name")
            if name not in deps or name in seen:
                continue
            doc_ver = match.group("ver")
            pin = deps[name]
            if _major_minor(doc_ver) == _major_minor(pin):
                continue
            seen.add(name)
            drifts.append({
                "file": fname,
                "tool": name,
                "doc_version": doc_ver,
                "sbt_version": pin,
                "detail": f"{name} {doc_ver} in {fname} should be {pin} (build.sbt)",
                "pos": match.start(),
            })
    return drifts
