"""Fix application: auto-correct detected drifts in documentation files."""
from __future__ import annotations
import re
from pathlib import Path

from .rust import DOC_RE, TOOLCHAIN_RE
from .node import NODE_RE
from .python import PY_RE
from .go import GO_RE
from .count import COUNT_RE


def apply_fixes(root: Path, result: dict) -> list[str]:
    """Apply fixes for all detected drifts. Returns list of fixed file paths."""
    fixed = []
    
    def fix_in_file(path: Path, old_ver: str, new_ver: str, patterns: list[re.Pattern]) -> bool:
        """Replace version in file. Returns True if modified."""
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
            path.write_text(text, encoding="utf-8")
            return True
        return False
    
    # Rust drifts (toolchain.toml source)
    for d in result.get("drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_version"], d["toolchain_version"], [DOC_RE]):
                fixed.append(d["file"])
    
    # Rust drifts (multi-source: toolchain.toml or Cargo.toml rust-version)
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
                fpath.write_text(text, encoding="utf-8")
                if d["file"] not in fixed:
                    fixed.append(d["file"])

    # Line-ending drifts: ensure .gitattributes normalizes CRLF
    for d in result.get("lineending_drifts", []):
        ga = root / d["file"]
        needed = "* text=auto eol=lf\n"
        if not ga.exists():
            ga.write_text("# Normalize line endings so working-tree bytes match the index on every platform\n" + needed)
            fixed.append(d["file"])
        else:
            text = ga.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            if "text=auto eol=lf" not in text:
                text = text.rstrip("\n") + "\n\n# Normalize line endings (added by driftcheck --fix)\n" + needed
                ga.write_text(text, encoding="utf-8")
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
                fpath.write_text(text, encoding="utf-8")
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
                fpath.write_text(text, encoding="utf-8")
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
                fpath.write_text(text, encoding="utf-8")
                fixed.append(d["file"])

    return fixed
