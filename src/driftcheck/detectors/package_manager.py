"""Package manager drift detection: packageManager field vs lockfile.

Detects drift between the packageManager field in package.json (corepack)
and the actual package manager used (based on lockfile presence).
"""
from __future__ import annotations
import re

# Match package manager mentions in README
PACKAGE_MANAGER_RE = re.compile(
    r'(?:npm|yarn|pnpm|bun)\s*[:=]?\s*(?P<version>\d[\d.]*)',
    re.I,
)


def parse_package_manager_field(text: str) -> str | None:
    """Extract packageManager field from package.json."""
    m = re.search(r'"packageManager"\s*:\s*"([^"]+)"', text)
    if m:
        return m.group(1)
    return None


def detect_lockfile_manager(root) -> str | None:
    """Detect which package manager is actually used based on lockfiles."""
    lockfiles = {
        "bun.lockb": "bun",
        "bun.lock": "bun",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
        "npm-shrinkwrap.json": "npm",
    }
    for lockfile, manager in lockfiles.items():
        if (root / lockfile).exists():
            return manager
    return None


def find_package_manager_drift(
    package_json_content: str | None,
    root,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between packageManager field and actual usage."""
    drifts = []
    
    if not package_json_content:
        return drifts
    
    pm_field = parse_package_manager_field(package_json_content)
    if not pm_field:
        return drifts
    
    # Extract manager from packageManager field (e.g., "pnpm@8.0.0" -> "pnpm")
    pm_manager = pm_field.split("@")[0] if "@" in pm_field else pm_field
    
    # Detect actual manager from lockfile
    actual_manager = detect_lockfile_manager(root)
    
    if actual_manager and actual_manager != pm_manager:
        drifts.append({
            "file": "package.json",
            "detail": f"packageManager={pm_manager} but {actual_manager} lockfile found",
            "package_manager_field": pm_manager,
            "actual_manager": actual_manager,
        })
    
    # Check README mentions
    for doc_fname, doc_content in docs.items():
        for m in PACKAGE_MANAGER_RE.finditer(doc_content):
            doc_pm = m.group(0).split()[0].lower()
            if doc_pm != pm_manager and doc_pm in ("npm", "yarn", "pnpm", "bun"):
                # Check if it's a version mention or manager mention
                ver = m.group("version") if m.group("version") else None
                if ver is None:
                    # Just a manager mention like "use pnpm"
                    if doc_pm != actual_manager:
                        drifts.append({
                            "file": doc_fname,
                            "detail": f"README mentions {doc_pm} but packageManager={pm_manager}",
                            "doc_manager": doc_pm,
                            "package_manager_field": pm_manager,
                        })
                        break
    
    return drifts
