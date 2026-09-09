"""PNPM workspace drift detection: pnpm-workspace.yaml vs package.json workspaces."""
from __future__ import annotations
import re

# Match workspace mentions in README
WORKSPACE_RE = re.compile(
    r'(?:workspace|workspaces|monorepo)\s*[:=]?\s*(?P<count>\d+)',
    re.I,
)


def parse_pnpm_workspace(text: str) -> list[str] | None:
    """Return workspace globs from pnpm-workspace.yaml."""
    packages = []
    in_packages = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "packages:":
            in_packages = True
            continue
        if in_packages:
            if stripped.startswith("-"):
                glob = stripped[1:].strip().strip('"').strip("'")
                if glob:
                    packages.append(glob)
            else:
                break
    return packages if packages else None


def find_pnpm_workspace_drift(
    pnpm_workspace_content: str | None,
    package_json_content: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between pnpm-workspace.yaml and package.json workspaces."""
    drifts = []

    # Check pnpm-workspace.yaml vs package.json workspaces
    if pnpm_workspace_content and package_json_content:
        pnpm_packages = parse_pnpm_workspace(pnpm_workspace_content)
        if pnpm_packages:
            # Extract workspaces from package.json
            pkg_workspaces = _extract_package_json_workspaces(package_json_content)
            if pkg_workspaces is not None and set(pnpm_packages) != set(pkg_workspaces):
                drifts.append({
                    "file": "package.json",
                    "tool": "pnpm",
                    "pnpm_packages": pnpm_packages,
                    "package_json_workspaces": pkg_workspaces,
                    "detail": f"pnpm-workspace.yaml has {pnpm_packages} but package.json has {pkg_workspaces}",
                    "pos": 0,
                })

    return drifts


def _extract_package_json_workspaces(text: str) -> list[str] | None:
    """Extract workspaces array from package.json text."""
    # Simple extraction — look for "workspaces": [...]
    m = re.search(r'"workspaces"\s*:\s*\[([^\]]*)\]', text)
    if m:
        items = re.findall(r'"([^"]+)"', m.group(1))
        return items if items else None
    # Also check "workspaces": { "packages": [...] }
    m = re.search(r'"workspaces"\s*:\s*\{[^}]*"packages"\s*:\s*\[([^\]]*)\]', text)
    if m:
        items = re.findall(r'"([^"]+)"', m.group(1))
        return items if items else None
    return None
