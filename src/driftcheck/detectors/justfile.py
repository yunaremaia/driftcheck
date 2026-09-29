"""Drift between justfile tool pins and README/docs mentions."""
from __future__ import annotations

import re

_VERSION_ANN_RE = re.compile(
    r"^\s*@version\s+(?P<tool>[A-Za-z][\w+-]*)@(?P<ver>\d+(?:\.\d+)*)",
    re.M,
)
_ASSIGN_RE = re.compile(
    r"""^\s*(?P<var>[A-Za-z_][\w]*)\s*:?=\s*["'](?P<value>[^"']+)["']""",
    re.M,
)
_VALUE_AT_RE = re.compile(
    r"^(?P<tool>[A-Za-z][\w+-]*)@(?P<ver>\d+(?:\.\d+)*)$"
)
_VALUE_SUFFIX_RE = re.compile(
    r"^(?P<tool>python|node|ruby|java|go|cmake)(?P<ver>\d+(?:\.\d+)+)$",
    re.I,
)

_DOC_NAMES = {
    "python": r"Python",
    "node": r"Node(?:\.js)?",
    "go": r"Go",
    "ruby": r"Ruby",
    "java": r"Java",
    "rust": r"Rust",
    "cargo": r"Rust",
    "cmake": r"CMake",
    "gcc": r"GCC",
}


def _major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}.{parts[1]}"


def parse_justfile_versions(text: str) -> dict[str, str]:
    """Return {tool: version} pins from a justfile."""
    pins: dict[str, str] = {}
    for match in _VERSION_ANN_RE.finditer(text):
        pins[match.group("tool").lower()] = match.group("ver")
    for match in _ASSIGN_RE.finditer(text):
        value = match.group("value").strip()
        parsed = _VALUE_AT_RE.match(value) or _VALUE_SUFFIX_RE.match(value)
        if not parsed:
            continue
        tool = parsed.group("tool").lower()
        pins.setdefault(tool, parsed.group("ver"))
    return pins


def find_justfile_drift(justfiles: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect justfile tool pins that disagree with documentation."""
    pins: dict[str, str] = {}
    for content in justfiles.values():
        for tool, version in parse_justfile_versions(content).items():
            pins.setdefault(tool, version)
    if not pins:
        return []

    drifts: list[dict] = []
    for tool, version in pins.items():
        label = _DOC_NAMES.get(tool)
        if not label:
            continue
        pattern = re.compile(
            rf"\b{label}\s+(?P<ver>\d+(?:\.\d+){{0,2}})\b",
            re.I,
        )
        pinned = _major_minor(version)
        for fname, content in docs.items():
            for match in pattern.finditer(content):
                doc_ver = match.group("ver")
                if _major_minor(doc_ver) == pinned:
                    continue
                drifts.append({
                    "file": fname,
                    "tool": tool,
                    "doc_version": doc_ver,
                    "justfile_version": version,
                    "detail": (
                        f"{tool} {doc_ver} in {fname} should be {version} (justfile)"
                    ),
                    "pos": match.start(),
                })
                break
    return drifts
