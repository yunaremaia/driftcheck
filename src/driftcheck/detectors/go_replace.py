"""Go drift between go.mod require/replace/exclude and go.sum resolutions."""
from __future__ import annotations

import re

_REQUIRE_LINE_RE = re.compile(
    r"^\s*(?:require\s+)?(?P<path>[A-Za-z0-9][A-Za-z0-9._/\-]*)\s+(?P<ver>v[0-9][^\s]+)",
    re.M,
)
_REPLACE_RE = re.compile(
    r"^\s*replace\s+(?P<path>\S+)(?:\s+(?P<from>v\S+))?\s*=>\s*(?P<target>\S+)(?:\s+(?P<to>v\S+))?",
    re.M,
)
_EXCLUDE_RE = re.compile(
    r"^\s*exclude\s+(?P<path>\S+)\s+(?P<ver>v\S+)",
    re.M,
)
_SUM_RE = re.compile(
    r"^(?P<path>\S+)\s+(?P<ver>v\S+?)(?:/go\.mod)?\s+\S+",
    re.M,
)


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def parse_go_requires(text: str) -> dict[str, str]:
    """Return {module path: version} from require directives, including blocks."""
    cleaned = _strip_comments(text)
    found: dict[str, str] = {}
    in_block = False
    for raw in cleaned.splitlines():
        stripped = raw.strip()
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if in_block or stripped.startswith("require "):
            match = _REQUIRE_LINE_RE.match(stripped if in_block else stripped)
            if match and match.group("path") != "require":
                found[match.group("path")] = match.group("ver")
    return found


def parse_go_replaces(text: str) -> list[dict[str, str]]:
    """Return replace directives. Local paths have an empty ``to`` version."""
    found = []
    for match in _REPLACE_RE.finditer(_strip_comments(text)):
        found.append({
            "path": match.group("path"),
            "from": match.group("from") or "",
            "target": match.group("target"),
            "to": match.group("to") or "",
        })
    return found


def parse_go_excludes(text: str) -> list[tuple[str, str]]:
    return [
        (match.group("path"), match.group("ver"))
        for match in _EXCLUDE_RE.finditer(_strip_comments(text))
    ]


def parse_go_sum(text: str) -> dict[str, set[str]]:
    """Return {module path: {versions}} recorded in go.sum."""
    found: dict[str, set[str]] = {}
    for match in _SUM_RE.finditer(text):
        found.setdefault(match.group("path"), set()).add(match.group("ver"))
    return found


def _is_local(target: str) -> bool:
    return target.startswith(".") or target.startswith("/") or target.startswith("\\")


def find_go_replace_drift(gomod_text: str, gosum_text: str) -> list[dict]:
    """Flag require versions missing from go.sum, version replaces, and excluded requires.

    A missing go.sum file is ignored. Local ``replace => ./fork`` directives are
    intentional and are not reported.
    """
    if not gomod_text.strip() or not gosum_text.strip():
        return []
    requires = parse_go_requires(gomod_text)
    summed = parse_go_sum(gosum_text)
    drifts: list[dict] = []

    for path, version in sorted(requires.items()):
        versions = summed.get(path, set())
        if version in versions:
            continue
        if not versions:
            detail = f"{path} {version} is required in go.mod but missing from go.sum"
        else:
            listed = ", ".join(sorted(versions))
            detail = f"{path} requires {version} in go.mod but go.sum has {listed}"
        drifts.append({
            "file": "go.mod",
            "package": path,
            "require_version": version,
            "detail": detail,
            "pos": 0,
        })

    required_versions = {(path, version) for path, version in requires.items()}
    for item in parse_go_replaces(gomod_text):
        if _is_local(item["target"]) or not item["to"]:
            continue
        declared = item["from"] or requires.get(item["path"], "")
        if declared and item["to"] != declared:
            drifts.append({
                "file": "go.mod",
                "package": item["path"],
                "require_version": declared,
                "replace_version": item["to"],
                "detail": (
                    f"{item['path']} requires {declared} but is replaced with {item['to']}"
                ),
                "pos": 0,
            })

    for path, version in parse_go_excludes(gomod_text):
        if (path, version) in required_versions:
            drifts.append({
                "file": "go.mod",
                "package": path,
                "require_version": version,
                "detail": f"{path} {version} is both required and excluded in go.mod",
                "pos": 0,
            })
    return drifts
