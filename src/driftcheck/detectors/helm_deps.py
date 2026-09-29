"""Helm chart dependency drift: Chart.yaml constraints vs Chart.lock versions.

Upstream chart indexes are not queried. A missing Chart.lock is ignored.
"""
from __future__ import annotations

import re

_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+|\*|x|X))?(?:\.(\d+|\*|x|X))?")
_CONSTRAINT_RE = re.compile(r"(>=|<=|>|<|~|\^|=)?\s*(\d+(?:\.(?:\d+|x|X|\*)){0,2})")


def _parse_blocks(text: str) -> list[dict[str, str]]:
    """Parse a dependencies list of name/version mappings without a YAML library."""
    deps: list[dict[str, str]] = []
    in_deps = False
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.strip().startswith("#") or not raw.strip():
            continue
        if re.match(r"^dependencies:\s*$", raw.strip()):
            in_deps = True
            current = None
            continue
        if not in_deps:
            continue
        if raw and not raw[0].isspace() and not raw.lstrip().startswith("-"):
            break
        item = re.match(r"^\s*-\s+name:\s*[\"']?([^\"'#]+)[\"']?\s*$", raw)
        if item:
            if current:
                deps.append(current)
            current = {"name": item.group(1).strip()}
            continue
        if current is None:
            continue
        field = re.match(r"^\s+(?:-\s+)?(version|name):\s*[\"']?([^\"'#]+)[\"']?\s*$", raw)
        if field:
            current[field.group(1)] = field.group(2).strip()
    if current:
        deps.append(current)
    return [dep for dep in deps if dep.get("name") and dep.get("version")]


def _parts(token: str) -> list[str]:
    match = _VERSION_RE.search(token)
    if not match:
        return []
    return [part if part is not None else "x" for part in match.groups()]


def _satisfies(locked: str, constraint: str) -> bool:
    got = _parts(locked)
    if not got:
        return True
    checks = list(_CONSTRAINT_RE.finditer(constraint.replace(" ", "")))
    if not checks:
        return True
    for match in checks:
        op = match.group(1) or "="
        bound = _parts(match.group(2))
        if not bound:
            continue
        if op in {"=", "=="}:
            for index, piece in enumerate(bound):
                if piece.lower() in {"x", "*"}:
                    continue
                if index >= len(got) or got[index] != piece:
                    return False
            continue
        if op == "^":
            if got[0] != bound[0]:
                return False
            continue
        # Numeric comparison on the components that are digits.
        def _tuple(parts: list[str]) -> tuple[int, ...]:
            nums = []
            for part in parts:
                if part.lower() in {"x", "*"}:
                    break
                if part.isdigit():
                    nums.append(int(part))
            return tuple(nums)

        left, right = _tuple(got), _tuple(bound)
        if op == ">=" and left < right:
            return False
        if op == ">" and left <= right:
            return False
        if op == "<=" and left > right:
            return False
        if op == "<" and left >= right:
            return False
        if op == "~":
            if not left or not right or left[0] != right[0]:
                return False
            if len(right) > 1 and len(left) > 1 and left[1] != right[1]:
                return False
    return True


def find_helm_dependency_drift(chart_text: str, lock_text: str) -> list[dict]:
    """Flag Chart.lock versions that fall outside Chart.yaml dependency constraints."""
    if not chart_text.strip() or not lock_text.strip():
        return []
    declared = {dep["name"]: dep["version"] for dep in _parse_blocks(chart_text)}
    locked = {dep["name"]: dep["version"] for dep in _parse_blocks(lock_text)}
    if not declared or not locked:
        return []
    drifts: list[dict] = []
    for name, constraint in sorted(declared.items()):
        version = locked.get(name)
        if version is None:
            drifts.append({
                "file": "Chart.lock",
                "package": name,
                "constraint": constraint,
                "detail": f"{name} {constraint} is in Chart.yaml but missing from Chart.lock",
                "pos": 0,
            })
            continue
        if _satisfies(version, constraint):
            continue
        drifts.append({
            "file": "Chart.lock",
            "package": name,
            "constraint": constraint,
            "lock_version": version,
            "detail": (
                f"{name} is locked at {version}, which does not satisfy "
                f"Chart.yaml constraint {constraint}"
            ),
            "pos": 0,
        })
    return drifts
