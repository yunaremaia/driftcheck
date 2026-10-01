"""Drift between dependency ranges across npm/pnpm/yarn workspace package.json files."""
from __future__ import annotations

import json
import re
from pathlib import Path

_DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_PKG_LINE_RE = re.compile(r"^\s*-\s+[\"']?([^\"'#]+)[\"']?\s*$")


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def workspace_patterns(root: Path) -> list[str]:
    """Collect workspace globs from package.json and pnpm-workspace.yaml."""
    patterns: list[str] = []
    package_json = root / "package.json"
    data = _read_json(package_json) if package_json.is_file() else None
    if data:
        workspaces = data.get("workspaces")
        if isinstance(workspaces, list):
            patterns.extend(str(item) for item in workspaces)
        elif isinstance(workspaces, dict):
            packages = workspaces.get("packages")
            if isinstance(packages, list):
                patterns.extend(str(item) for item in packages)
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        in_packages = False
        for raw in pnpm.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if stripped == "packages:":
                in_packages = True
                continue
            if in_packages:
                match = _PKG_LINE_RE.match(raw)
                if match:
                    patterns.append(match.group(1).strip())
                elif not raw.startswith(" ") and not raw.startswith("-"):
                    in_packages = False
    # preserve order, drop duplicates
    seen: set[str] = set()
    unique: list[str] = []
    for pattern in patterns:
        if pattern not in seen:
            seen.add(pattern)
            unique.append(pattern)
    return unique


def _package_json_paths(root: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    root_pkg = root / "package.json"
    if root_pkg.is_file():
        found.append(root_pkg)
        seen.add(root_pkg.resolve())
    for pattern in patterns:
        glob = pattern.strip().rstrip("/")
        if not glob.endswith("package.json"):
            glob = f"{glob}/package.json"
        for path in root.glob(glob):
            if not path.is_file() or "node_modules" in path.parts:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(path)
    return found


def _deps(data: dict) -> dict[str, str]:
    collected: dict[str, str] = {}
    for key in _DEP_KEYS:
        block = data.get(key)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if isinstance(spec, str):
                collected[str(name)] = spec.strip()
    return collected


def find_npm_workspace_drift(root: Path) -> list[dict]:
    """Flag the same dependency declared with different ranges across workspaces."""
    patterns = workspace_patterns(root)
    if not patterns:
        return []
    ranges: dict[str, dict[str, str]] = {}
    for path in _package_json_paths(root, patterns):
        data = _read_json(path)
        if not data:
            continue
        rel = path.relative_to(root).as_posix()
        for name, spec in _deps(data).items():
            ranges.setdefault(name, {})[rel] = spec

    drifts: list[dict] = []
    for name in sorted(ranges):
        specs = ranges[name]
        if len(specs) < 2:
            continue
        if len(set(specs.values())) < 2:
            continue
        rendered = ", ".join(f"{path}={spec}" for path, spec in sorted(specs.items()))
        first = sorted(specs)[0]
        drifts.append({
            "file": first,
            "package": name,
            "versions": specs,
            "detail": f"{name} has conflicting workspace ranges: {rendered}",
            "pos": 0,
        })
    return drifts
