"""Detect version drift between docs and toolchain files."""
from __future__ import annotations
import re
from pathlib import Path
import json

TOOLCHAIN_RE = re.compile(r'channel\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"')
DOC_RE = re.compile(r'Rust\s+(?P<ver>[0-9]+\.[0-9]+\.[0-9]+)')

def parse_toolchain_version(text: str) -> str | None:
    m = TOOLCHAIN_RE.search(text)
    return m.group("ver") if m else None

def find_rust_drift(toolchain_text: str, docs: dict[str, str]) -> list[dict]:
    """Return list of drifts vs a rust-toolchain.toml source.

    Delegates to find_rust_drift_multi for consistent minor-aware comparison.
    """
    return find_rust_drift_multi(toolchain_text=toolchain_text, cargo_text="", docs=docs)


CARGO_RE = re.compile(r'rust-version\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"')

# Looser doc regex for multi-source: accepts major.minor (e.g. "Rust 1.96") too.
DOC_RE_LOOSE = re.compile(r'Rust\s+(?P<ver>[0-9]+(?:\.[0-9]+){1,2})')

def parse_cargo_rust_version(text: str) -> str | None:
    """Parse `rust-version = "1.96.1"` from Cargo.toml."""
    m = CARGO_RE.search(text)
    return m.group("ver") if m else None


def _minor(v: str) -> str:
    """Best-effort major.minor of a semver-ish string (handles '1.96' and '1.96.1')."""
    parts = v.split(".")
    return ".".join(parts[:2])


def find_rust_drift_multi(toolchain_text: str, cargo_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Rust doc drift using rust-toolchain.toml and/or Cargo.toml rust-version.

    A doc version drifts when it does not match the toolchain on the shared
    precision (full version if both have a patch, major.minor otherwise).
    Returns list of {file, doc_version, toolchain_version?, cargo_version?}.
    """
    tv = parse_toolchain_version(toolchain_text)
    cv = parse_cargo_rust_version(cargo_text)
    # resolve authoritative version: prefer toolchain, fall back to cargo
    if tv and cv:
        authoritative = tv if _minor(tv) == _minor(cv) or tv == cv else (tv if len(tv) >= len(cv) else cv)
    else:
        authoritative = tv or cv
    if not authoritative:
        return []
    # build comparison key: full if patch present, else major.minor
    auth_has_patch = authoritative.count(".") == 2
    auth_key = authoritative if auth_has_patch else _minor(authoritative)

    drifts = []
    for fname, content in docs.items():
        for m in DOC_RE_LOOSE.finditer(content):
            dv = m.group("ver")
            # When the authoritative version lacks a patch, compare on major.minor
            # only (so "1.96" and "1.96.1" are treated as matching).
            if not auth_has_patch:
                doc_key = _minor(dv)
            else:
                doc_key = dv if dv.count(".") == 2 else _minor(dv)
            if doc_key != auth_key:
                entry = {"file": fname, "doc_version": dv, "pos": m.start()}
                if tv:
                    entry["toolchain_version"] = tv
                if cv:
                    entry["cargo_version"] = cv
                drifts.append(entry)
                break  # one per file
    return drifts


NODE_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version)\s+Node(?:\.js)?\s+(?P<ver>[0-9]+(?:\.[0-9]+)?)',
    re.I
)
ENGINES_RE = re.compile(r'"node"\s*:\s*"(?P<ver>[^"]+)"')

def parse_node_version_from_package(text: str) -> str | None:
    try:
        data = json.loads(text)
        eng = data.get("engines", {}).get("node", "")
        if not eng:
            return None
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
            # Check if this match is on a numbered list line (1., 2., etc.) - common in TOC
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue  # Skip TOC/list numbering
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


GO_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version|build|test|with|requires)\s+Go\s+(?P<ver>[0-9]+\.[0-9]+)|(?<=\s)Go\s+(?P<ver2>[0-9]+\.[0-9]+)(?=\s|$|,|\.|;)(?!\s+(?:and|or)\s+(?:later|earlier))',
    re.I
)
GO_MOD_RE = re.compile(r'^\s*go\s+(?P<ver>[0-9]+\.[0-9]+)', re.MULTILINE)

def parse_go_version_from_gomod(text: str) -> str | None:
    m = GO_MOD_RE.search(text)
    return m.group("ver") if m else None

def find_go_drift(gomod_text: str, docs: dict[str, str]) -> list[dict]:
    gv = parse_go_version_from_gomod(gomod_text)
    if not gv:
        return []
    # Normalize go.mod version to major.minor
    gv_minor = ".".join(gv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in GO_RE.finditer(content):
            dv = m.group("ver")
            # Check if this match is on a numbered list line
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue  # Skip TOC/list numbering
            if dv != gv_minor:
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
    cargo_path = root / "Cargo.toml"
    cargo_text = cargo_path.read_text(encoding="utf-8", errors="replace") if cargo_path.exists() else ""
    
    rust_drifts = find_rust_drift(toolchain_text, docs)
    rust_drifts_multi = find_rust_drift_multi(toolchain_text, cargo_text, docs)
    node_drifts = find_node_drift(package_text, docs)
    python_drifts = find_python_drift(pyproject_text, docs)
    go_drifts = find_go_drift(gomod_text, docs)
    
    return {
        "toolchain_version": parse_toolchain_version(toolchain_text),
        "cargo_rust_version": parse_cargo_rust_version(cargo_text),
        "package_node": parse_node_version_from_package(package_text),
        "pyproject_python": parse_python_version_from_pyproject(pyproject_text),
        "gomod_version": parse_go_version_from_gomod(gomod_text),
        "drifts": rust_drifts,
        "rust_drifts": rust_drifts_multi,
        "node_drifts": node_drifts,
        "python_drifts": python_drifts,
        "go_drifts": go_drifts,
    }