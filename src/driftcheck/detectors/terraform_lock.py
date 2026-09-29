"""Drift between Terraform required_providers constraints and .terraform.lock.hcl.

Registry lookups stay off. The detector only checks that the locked version
satisfies the constraint declared in ``.tf`` files.
"""
from __future__ import annotations

import re

_PROVIDER_BLOCK_RE = re.compile(
    r"(?P<name>[A-Za-z0-9_-]+)\s*=\s*\{(?P<body>[^{}]*)\}",
    re.S,
)
_SOURCE_RE = re.compile(r'source\s*=\s*"(?P<source>[^"]+)"')
_VERSION_RE = re.compile(r'version\s*=\s*"(?P<ver>[^"]+)"')
_LOCK_RE = re.compile(
    r'provider\s+"(?P<source>[^"]+)"\s*\{[^}]*?version\s*=\s*"(?P<ver>[^"]+)"',
    re.S,
)
_CONSTRAINT_RE = re.compile(
    r"(?P<op>>=|<=|!=|~>|=|>|<)\s*(?P<ver>\d+(?:\.\d+)*)"
)


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split(".") if part.isdigit())


def _cmp(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def _normalize_source(source: str) -> str:
    prefix = "registry.terraform.io/"
    if source.startswith(prefix):
        return source[len(prefix):]
    return source


def parse_required_providers(text: str) -> dict[str, str]:
    """Return {source: version constraint} from Terraform required_providers."""
    found: dict[str, str] = {}
    for match in _PROVIDER_BLOCK_RE.finditer(text):
        body = match.group("body")
        source = _SOURCE_RE.search(body)
        version = _VERSION_RE.search(body)
        if source and version:
            found[_normalize_source(source.group("source"))] = version.group("ver")
    return found


def parse_lock_versions(text: str) -> dict[str, str]:
    """Return {source: locked version} from .terraform.lock.hcl."""
    found: dict[str, str] = {}
    for match in _LOCK_RE.finditer(text):
        found[_normalize_source(match.group("source"))] = match.group("ver")
    return found


def _satisfies(version: str, constraint: str) -> bool:
    got = _version_tuple(version)
    if not got:
        return True
    checks = list(_CONSTRAINT_RE.finditer(constraint))
    if not checks:
        return True
    for match in checks:
        op = match.group("op")
        bound = _version_tuple(match.group("ver"))
        cmp = _cmp(got, bound)
        if op in {"=", "=="} and cmp != 0:
            return False
        if op == "!=" and cmp == 0:
            return False
        if op == ">=" and cmp < 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == "<" and cmp >= 0:
            return False
        if op == "~>":
            if cmp < 0:
                return False
            if len(bound) >= 3:
                ceiling = (bound[0], bound[1] + 1)
            elif len(bound) == 2:
                ceiling = (bound[0] + 1,)
            else:
                ceiling = (bound[0] + 1,)
            if _cmp(got, ceiling) >= 0:
                return False
    return True


def find_terraform_lock_drift(
    terraform_files: dict[str, str],
    lock_text: str,
) -> list[dict]:
    """Flag locked provider versions that fall outside declared constraints."""
    if not lock_text.strip():
        return []
    constraints: dict[str, str] = {}
    for content in terraform_files.values():
        constraints.update(parse_required_providers(content))
    if not constraints:
        return []
    locked = parse_lock_versions(lock_text)
    drifts: list[dict] = []
    for source, constraint in sorted(constraints.items()):
        version = locked.get(source)
        if not version or _satisfies(version, constraint):
            continue
        drifts.append({
            "file": ".terraform.lock.hcl",
            "provider": source,
            "lock_version": version,
            "constraint": constraint,
            "detail": (
                f"{source} is locked at {version}, which does not satisfy "
                f"required_providers constraint {constraint}"
            ),
            "pos": 0,
        })
    return drifts
