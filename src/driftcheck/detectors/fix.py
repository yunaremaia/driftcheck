"""Fix application: auto-correct detected drifts in documentation files."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from .rust import DOC_RE, TOOLCHAIN_RE
from .node import NODE_RE
from .python import PY_RE
from .go import GO_RE
from .count import COUNT_RE


def _atomic_write(path: Path, content: str, backup_dir: Path | None = None) -> None:
    """Write content atomically to path with optional backup.

    Writes to a temp file first, then os.replace() for atomicity.
    If backup_dir is provided, backs up the original file before overwriting.
    """
    path = Path(path)

    # Create backup if requested and file exists
    if backup_dir is not None and path.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)  # millisecond precision
        backup_path = backup_dir / f"{path.name}.{timestamp}"
        shutil.copy2(path, backup_path)

    # Atomic write: write to temp file, then replace
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".driftcheck-tmp",
        dir=str(path.parent),
        prefix=f".{path.name}."
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def apply_fixes(root: Path, result: dict, *, backup: bool = True) -> list[str]:
    """Apply fixes for all detected drifts. Returns list of fixed file paths.

    Args:
        root: Repository root path
        result: Scan result dict from scan_repo()
        backup: If True (default), back up original files before modification.
                Set to False in CI environments to skip backup creation.
    """
    fixed = []
    backup_dir: Path | None = None
    if backup:
        backup_dir = Path(root) / ".driftcheck-backups"

    def fix_in_file(path: Path, old_ver: str, new_ver: str, patterns: list[re.Pattern]) -> bool:
        """Replace version in file atomically with backup. Returns True if modified."""
        text = path.read_text(encoding="utf-8", errors="replace")
        original = text
        for pat in patterns:
            # Only replace the version number, keep the rest
            def repl(match):
                # Find the version group in the matched text
                matched = match.group(0)
                return matched.replace(old_ver, new_ver, 1)
            text = pat.sub(repl, text)
        if text != original:
            _atomic_write(path, text, backup_dir=backup_dir)
            return True
        return False

    # Rust drifts (drifts key is now an alias for rust_drifts — both point to multi-source results)
    # We only process rust_drifts here to avoid double-fixing
    for d in result.get("rust_drifts", []):
        fpath = root / d["file"]
        target = d.get("toolchain_version") or d.get("cargo_version")
        if fpath.exists() and target:
            if fix_in_file(fpath, d["doc_version"], target, [DOC_RE]):
                fixed.append(d["file"])

    # Node drifts
    for d in result.get("node_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_version"], d["package_version"], [NODE_RE]):
                fixed.append(d["file"])

    # Python drifts
    for d in result.get("python_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_version"], d["pyproject_version"], [PY_RE]):
                fixed.append(d["file"])

    # Go drifts
    for d in result.get("go_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_version"], d["gomod_version"], [GO_RE]):
                fixed.append(d["file"])

    # Count drifts (skills directory count)
    for d in result.get("count_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_count"], str(d["actual_count"]), [COUNT_RE]):
                if d["file"] not in fixed:
                    fixed.append(d["file"])

    # Actions Node drifts: bump GitHub Actions from node20 to node24
    for d in result.get("actions_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8", errors="replace")
            # replace the specific deprecated version with fixed
            old = f"{d['action']}@{d['current']}"
            new = f"{d['action']}@{d['suggested']}"
            if old in text:
                text = text.replace(old, new)
                _atomic_write(fpath, text, backup_dir=backup_dir)
                if d["file"] not in fixed:
                    fixed.append(d["file"])

    # Line-ending drifts: ensure .gitattributes normalizes CRLF
    for d in result.get("lineending_drifts", []):
        ga = root / d["file"]
        needed = "* text=auto eol=lf\n"
        if not ga.exists():
            _atomic_write(ga, "# Normalize line endings so working-tree bytes match the index on every platform\n" + needed, backup_dir=backup_dir)
            fixed.append(d["file"])
        else:
            text = ga.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            if "text=auto eol=lf" not in text:
                text = text.rstrip("\n") + "\n\n# Normalize line endings (added by driftcheck --fix)\n" + needed
                _atomic_write(ga, text, backup_dir=backup_dir)
                fixed.append(d["file"])

    # GitHub Actions version drifts: bump outdated action versions
    for d in result.get("gh_actions_version_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8", errors="replace")
            old = f"{d['action']}@{d['current']}"
            new = f"{d['action']}@{d['suggested']}"
            if old in text:
                text = text.replace(old, new)
                _atomic_write(fpath, text, backup_dir=backup_dir)
                if d["file"] not in fixed:
                    fixed.append(d["file"])

    # Helm drifts
    for d in result.get("helm_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8", errors="replace")
            old = d["doc_version"]
            new = d["helm_image"]
            if old in text:
                text = text.replace(old, new, 1)
                _atomic_write(fpath, text, backup_dir=backup_dir)
                fixed.append(d["file"])

    # Docker Compose drifts
    for d in result.get("dc_drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8", errors="replace")
            old = d["doc_version"]
            new = d["compose_image"]
            if old in text:
                text = text.replace(old, new, 1)
                _atomic_write(fpath, text, backup_dir=backup_dir)
                fixed.append(d["file"])

    return fixed
