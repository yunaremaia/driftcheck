"""Drift between Python version pins inside pyproject.toml [tool.*] tables.

Compares ``requires-python`` with tool target versions such as
``[tool.ruff] target-version``, ``[tool.black] target-version``, and
``[tool.mypy] python_version``.
"""
from __future__ import annotations

import re

_REQUIRES_RE = re.compile(
    r"^requires-python\s*=\s*[\"']([^\"']+)[\"']",
    re.M,
)
_VERSION_RE = re.compile(r"(\d+)\.(\d+)")
_PY_TAG_RE = re.compile(r"py(\d)(\d{2})\b|py(\d+)\.(\d+)\b", re.I)
_TARGET_RE = re.compile(
    r"^target-version\s*=\s*(.+)$",
    re.I,
)
_MYPY_RE = re.compile(
    r"^(?:python_version|pythonVersion)\s*=\s*[\"']([^\"']+)[\"']",
    re.I,
)


def _tag_to_version(token: str) -> str | None:
    tag = _PY_TAG_RE.search(token)
    if tag:
        if tag.group(1):
            return f"{tag.group(1)}.{int(tag.group(2))}"
        return f"{tag.group(3)}.{tag.group(4)}"
    match = _VERSION_RE.search(token)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None


def _floor(spec: str) -> str | None:
    match = _VERSION_RE.search(spec)
    if not match:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def parse_tool_python_versions(text: str) -> dict[str, str]:
    """Return {source: major.minor} for requires-python and tool targets."""
    found: dict[str, str] = {}
    section = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        if section == "project":
            match = _REQUIRES_RE.match(stripped)
            if match:
                floor = _floor(match.group(1))
                if floor:
                    found["requires-python"] = floor
            continue
        if section in {"tool.ruff", "tool.black"}:
            match = _TARGET_RE.match(stripped)
            if match:
                version = _tag_to_version(match.group(1))
                if version:
                    tool = section.split(".", 1)[1]
                    found[tool] = version
            continue
        if section in {"tool.mypy", "tool.pyright"}:
            match = _MYPY_RE.match(stripped)
            if match:
                version = _tag_to_version(match.group(1))
                if version:
                    tool = section.split(".", 1)[1]
                    found[tool] = version
    return found


def find_pyproject_tool_drift(pyproject_text: str) -> list[dict]:
    """Detect disagreeing Python targets inside one pyproject.toml.

    When ``requires-python`` is set, every tool target is compared to that
    floor. Otherwise tool targets are compared to each other.
    """
    versions = parse_tool_python_versions(pyproject_text)
    if len(versions) < 2:
        return []

    drifts: list[dict] = []
    floor = versions.get("requires-python")
    if floor:
        for tool, version in versions.items():
            if tool == "requires-python" or version == floor:
                continue
            drifts.append({
                "file": "pyproject.toml",
                "tool": tool,
                "doc_version": version,
                "config_version": floor,
                "detail": (
                    f"[tool.{tool}] targets Python {version} but "
                    f"requires-python floor is {floor}"
                ),
                "pos": 0,
            })
        return drifts

    baseline_tool, baseline = next(iter(versions.items()))
    for tool, version in versions.items():
        if tool == baseline_tool or version == baseline:
            continue
        drifts.append({
            "file": "pyproject.toml",
            "tool": tool,
            "doc_version": version,
            "config_version": baseline,
            "detail": (
                f"[tool.{tool}] targets Python {version} but "
                f"[tool.{baseline_tool}] targets Python {baseline}"
            ),
            "pos": 0,
        })
    return drifts
