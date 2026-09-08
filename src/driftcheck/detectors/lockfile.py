"""Lockfile drift detection: missing, stale, or orphaned lockfiles."""
from __future__ import annotations
import os
from pathlib import Path

# Manifest -> lockfile mapping
MANIFEST_LOCKFILE = {
    "package.json": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb"],
    "Cargo.toml": ["Cargo.lock"],
    "go.mod": ["go.sum"],
    "Gemfile": ["Gemfile.lock"],
    "composer.json": ["composer.lock"],
    "requirements.txt": ["requirements.txt.lock", ".requirements.lock"],
    "pyproject.toml": ["poetry.lock", "uv.lock", "Pipfile.lock"],
}


def find_lockfile_drift(root: Path) -> list[dict]:
    """Detect lockfile drift: missing, stale, or orphaned lockfiles.

    A lockfile is:
    - **missing**: manifest exists but no lockfile found
    - **stale**: lockfile is older than the manifest (manifest changed without
      regenerating the lockfile)
    - **orphaned**: lockfile exists but no corresponding manifest

    Returns list of {file, kind, detail, pos}.
    """
    drifts = []

    for manifest, lockfiles in MANIFEST_LOCKFILE.items():
        manifest_path = root / manifest
        if not manifest_path.exists():
            # Check for orphaned lockfiles
            for lf in lockfiles:
                lf_path = root / lf
                if lf_path.exists():
                    drifts.append({
                        "file": lf,
                        "kind": "lockfile_orphaned",
                        "detail": f"orphaned {lf} — no {manifest} found",
                        "pos": 0,
                    })
            continue

        # Manifest exists — check for lockfiles
        found_lockfile = False
        for lf in lockfiles:
            lf_path = root / lf
            if lf_path.exists():
                found_lockfile = True
                # Check staleness (mtime comparison)
                try:
                    manifest_mtime = os.path.getmtime(manifest_path)
                    lockfile_mtime = os.path.getmtime(lf_path)
                    if lockfile_mtime < manifest_mtime:
                        drifts.append({
                            "file": lf,
                            "kind": "lockfile_stale",
                            "detail": f"stale {lf} — older than {manifest} (run package manager to regenerate)",
                            "pos": 0,
                        })
                except OSError:
                    pass

        if not found_lockfile:
            # No lockfile found for this manifest
            # Only flag for package managers where lockfiles are standard
            if manifest in ("package.json", "Cargo.toml", "go.mod", "Gemfile", "composer.json"):
                drifts.append({
                    "file": lockfiles[0],
                    "kind": "lockfile_missing",
                    "detail": f"missing {lockfiles[0]} — {manifest} exists but no lockfile found (run package manager install)",
                    "pos": 0,
                })

    return drifts
