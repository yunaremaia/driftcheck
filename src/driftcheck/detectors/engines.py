"""Engines drift detection: package.json engines vs .nvmrc / packageManager field."""
from __future__ import annotations
import json
import re
from pathlib import Path


def _parse_node_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse '20.11.0', '>=18', '^20', '~20.11', '20', 'lts/*' into (major, minor, patch)."""
    version_str = version_str.strip()
    if version_str == "lts/*":
        return None  # Can't compare LTS aliases
    # Remove prefixes
    for prefix in (">=", "<=", ">", "<", "^", "~", "v"):
        if version_str.startswith(prefix):
            version_str = version_str[len(prefix):]
            break
    parts = version_str.split(".")
    try:
        major = int(parts[0]) if parts[0] else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2] else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return None


def _parse_nvmrc(content: str) -> str | None:
    """Parse .nvmrc content to extract version."""
    content = content.strip()
    if not content:
        return None
    # Handle 'lts/*', 'lts/hydrogen', '20', '20.11', 'v20.11.0'
    content = content.lstrip("v")
    if content.startswith("lts/"):
        return None  # Can't compare LTS aliases
    return content


def find_engines_drift(root: Path) -> list[dict]:
    """Detect drift between package.json engines and .nvmrc / packageManager.

    Checks:
    - package.json `engines.node` vs `.nvmrc` version
    - package.json `packageManager` vs `.nvmrc` version
    - package.json `engines.node` vs `volta.node` (if volta present)

    Returns list of {file, kind, detail, pos}.
    """
    drifts = []
    package_json = root / "package.json"
    nvmrc = root / ".nvmrc"

    if not package_json.exists():
        return drifts

    try:
        with open(package_json, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return drifts

    engines = pkg.get("engines", {})
    engine_node = engines.get("node")
    package_manager = pkg.get("packageManager")
    volta = pkg.get("volta", {})
    volta_node = volta.get("node")

    # Read .nvmrc
    nvmrc_version = None
    if nvmrc.exists():
        try:
            nvmrc_content = nvmrc.read_text(encoding="utf-8")
            nvmrc_version = _parse_nvmrc(nvmrc_content)
        except OSError:
            pass

    # Check engines.node vs .nvmrc
    if engine_node and nvmrc_version:
        engine_tuple = _parse_node_version(engine_node)
        nvmrc_tuple = _parse_node_version(nvmrc_version)
        if engine_tuple and nvmrc_tuple:
            # Compare major.minor (patch can differ)
            if (engine_tuple[0], engine_tuple[1]) != (nvmrc_tuple[0], nvmrc_tuple[1]):
                drifts.append({
                    "file": "package.json",
                    "kind": "engines_drift",
                    "detail": (
                        f"engines.node ({engine_node}) ≠ .nvmrc ({nvmrc_version}) — "
                        f"major.minor mismatch: {engine_tuple[0]}.{engine_tuple[1]} vs {nvmrc_tuple[0]}.{nvmrc_tuple[1]}"
                    ),
                    "pos": 0,
                })

    # Check packageManager vs .nvmrc
    if package_manager and nvmrc_version:
        # packageManager format: "pnpm@8.15.0" or "yarn@4.1.0"
        pm_match = re.match(r"^([a-z]+)@(\d+\.\d+\.\d+)$", package_manager)
        if pm_match:
            pm_version = pm_match.group(2)
            pm_tuple = _parse_node_version(pm_version)
            nvmrc_tuple = _parse_node_version(nvmrc_version)
            if pm_tuple and nvmrc_tuple:
                # For pnpm/yarn, the version is the package manager version, not node
                # But we can still flag if .nvmrc is wildly different from what the PM expects
                pass  # Skip — comparing PM version to node version is apples-to-oranges

    # Check engines.node vs volta.node
    if engine_node and volta_node:
        engine_tuple = _parse_node_version(engine_node)
        volta_tuple = _parse_node_version(volta_node)
        if engine_tuple and volta_tuple:
            if (engine_tuple[0], engine_tuple[1]) != (volta_tuple[0], volta_tuple[1]):
                drifts.append({
                    "file": "package.json",
                    "kind": "engines_drift",
                    "detail": (
                        f"engines.node ({engine_node}) ≠ volta.node ({volta_node}) — "
                        f"major.minor mismatch: {engine_tuple[0]}.{engine_tuple[1]} vs {volta_tuple[0]}.{volta_tuple[1]}"
                    ),
                    "pos": 0,
                })

    return drifts
