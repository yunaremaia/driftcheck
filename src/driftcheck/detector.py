"""Detect version drift between docs and toolchain files."""
from __future__ import annotations
import re
from pathlib import Path
import json

TOOLCHAIN_RE = re.compile(r'channel\s*=\s*"(?P<ver>[0-9]+\.[0-9]+\.[0-9]+)"')
DOC_RE = re.compile(r'Rust\s+(?P<ver>[0-9]+\.[0-9]+\.[0-9]+)')

def parse_toolchain_version(text: str) -> str | None:
    m = TOOLCHAIN_RE.search(text)
    return m.group("ver") if m else None

def find_rust_drift(toolchain_text: str, docs: dict[str, str]) -> list[dict]:
    """Return list of drifts: each is {file, doc_version, toolchain_version}."""
    tv = parse_toolchain_version(toolchain_text)
    if not tv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in DOC_RE.finditer(content):
            dv = m.group("ver")
            if dv != tv:
                drifts.append({"file": fname, "doc_version": dv, "toolchain_version": tv, "pos": m.start()})
                break  # one per file
    return drifts


NODE_RE = re.compile(r'Node(?:\.js)?\s+(?P<ver>[0-9]+)(?:\.[0-9]+)?', re.I)
ENGINES_RE = re.compile(r'"node"\s*:\s*"(?P<ver>[^"]+)"')

def parse_node_version_from_package(text: str) -> str | None:
    try:
        data = json.loads(text)
        eng = data.get("engines", {}).get("node", "")
        if not eng:
            return None
        # extract first number: "24.x" -> 24, ">=24.0.0" -> 24
        m = re.search(r"[0-9]+", eng)
        return m.group(0) if m else None
    except Exception:
        return None

def find_node_drift(package_text: str, docs: dict[str, str]) -> list[dict]:
    pv = parse_node_version_from_package(package_text)
    if not pv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in NODE_RE.finditer(content):
            dv = m.group("ver")
            if dv != pv:
                drifts.append({"file": fname, "doc_version": dv, "package_version": pv, "pos": m.start()})
                break
    return drifts


PY_RE = re.compile(r'Python\s+(?P<ver>[0-9]+\.[0-9]+)', re.I)

def parse_python_version_from_pyproject(text: str) -> str | None:
    # naive parse: requires-python = ">=3.10" or ">=3.10,<3.13"
    m = re.search(r'requires-python\s*=\s*"[^"]*?([0-9]+\.[0-9]+)', text)
    if m:
        return m.group(1)
    # also PEP 621 via [project] requires-python
    return None

def find_python_drift(pyproject_text: str, docs: dict[str, str]) -> list[dict]:
    pv = parse_python_version_from_pyproject(pyproject_text)
    if not pv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in PY_RE.finditer(content):
            dv = m.group("ver")
            if dv != pv:
                drifts.append({"file": fname, "doc_version": dv, "pyproject_version": pv, "pos": m.start()})
                break
    return drifts


GO_RE = re.compile(r'Go\s+(?P<ver>[0-9]+\.[0-9]+)', re.I)
GO_MOD_RE = re.compile(r'^\s*go\s+(?P<ver>[0-9]+\.[0-9]+)', re.MULTILINE)

def parse_go_version_from_gomod(text: str) -> str | None:
    m = GO_MOD_RE.search(text)
    return m.group("ver") if m else None

def find_go_drift(gomod_text: str, docs: dict[str, str]) -> list[dict]:
    gv = parse_go_version_from_gomod(gomod_text)
    if not gv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in GO_RE.finditer(content):
            dv = m.group("ver")
            if dv != gv:
                drifts.append({"file": fname, "doc_version": dv, "gomod_version": gv, "pos": m.start()})
                break
    return drifts


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
    
    # Rust drifts
    for d in result.get("drifts", []):
        fpath = root / d["file"]
        if fpath.exists():
            if fix_in_file(fpath, d["doc_version"], d["toolchain_version"], [DOC_RE]):
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
    
    return fixed


def scan_repo(root: Path = Path(".")) -> dict:
    """Scan a repo on disk, return {toolchain_version, drifts}."""
    tc_path = root / "rust-toolchain.toml"
    toolchain_text = tc_path.read_text(encoding="utf-8", errors="replace") if tc_path.exists() else ""
    # collect doc files
    candidates = [root / "README.md", root / "CONTRIBUTING.md", root / "CONTRIBUTING-BEGINNERS.md"]
    candidates += list((root / "docs").glob("README*.md"))
    docs = {}
    for p in candidates:
        if p.exists():
            docs[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    pkg_path = root / "package.json"
    package_text = pkg_path.read_text(encoding="utf-8", errors="replace") if pkg_path.exists() else ""
    py_path = root / "pyproject.toml"
    pyproject_text = py_path.read_text(encoding="utf-8", errors="replace") if py_path.exists() else ""
    gomod_path = root / "go.mod"
    gomod_text = gomod_path.read_text(encoding="utf-8", errors="replace") if gomod_path.exists() else ""
    
    rust_drifts = find_rust_drift(toolchain_text, docs)
    node_drifts = find_node_drift(package_text, docs)
    python_drifts = find_python_drift(pyproject_text, docs)
    go_drifts = find_go_drift(gomod_text, docs)
    
    return {
        "toolchain_version": parse_toolchain_version(toolchain_text),
        "package_node": parse_node_version_from_package(package_text),
        "pyproject_python": parse_python_version_from_pyproject(pyproject_text),
        "gomod_version": parse_go_version_from_gomod(gomod_text),
        "drifts": rust_drifts,
        "node_drifts": node_drifts,
        "python_drifts": python_drifts,
        "go_drifts": go_drifts,
    }