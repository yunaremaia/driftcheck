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
    rust_drifts = find_rust_drift(toolchain_text, docs)
    node_drifts = find_node_drift(package_text, docs)
    return {"toolchain_version": parse_toolchain_version(toolchain_text), "package_node": parse_node_version_from_package(package_text), "drifts": rust_drifts, "node_drifts": node_drifts}
