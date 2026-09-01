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

def _vtuple(v: str) -> tuple[int, ...]:
    """Version string -> tuple of ints for comparison (e.g. '3.8' -> (3, 8))."""
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return (0,)


def find_python_drift(pyproject_text: str, docs: dict[str, str]) -> list[dict]:
    pv = parse_python_version_from_pyproject(pyproject_text)
    if not pv:
        return []
    pv_t = _vtuple(pv)
    drifts = []
    for fname, content in docs.items():
        for m in PY_RE.finditer(content):
            dv = m.group("ver")
            # Precision filter: skip non-requirement mentions like
            # "CPython 3.11 compatibility stack" or "PyTDC 1.1.15 on CPython 3.11"
            # which are package-specific stacks, not the repo's required Python.
            window_start = max(0, m.start() - 40)
            window_end = min(len(content), m.end() + 40)
            window = content[window_start:window_end].lower()
            if "cpython" in window or "compatibility stack" in window or "pyt" in window and "compatibility" in window:
                # double-check: only skip if CPython is near Python mention
                if "cpython" in content[max(0, m.start()-20):m.start()].lower():
                    continue
                if "compatibility" in window:
                    continue
            # requires-python is a *floor* (minimum supported). A doc that
            # mentions a version >= the floor is fine (e.g. an example using
            # 3.12 while requires-python is >=3.8). Only flag when the doc asks
            # for something BELOW the supported minimum — that means the README
            # is stale and understates what the project requires.
            if _vtuple(dv) < pv_t:
                drifts.append({"file": fname, "doc_version": dv, "pyproject_version": pv, "pos": m.start()})
                break
    return drifts


GO_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version|build|test|with|requires)\s+Go\s+(?P<ver>[0-9]+\.[0-9]+)|(?<=\s)Go\s+(?P<ver2>[0-9]+\.[0-9]+)(?=\s|$|,|\.|;)(?!\s+(?:and|or)\s+(?:later|earlier))',
    re.I
)
GO_MOD_RE = re.compile(r'^\s*go\s+(?P<ver>[0-9]+\.[0-9]+)', re.MULTILINE)


EOL_ATTR_RE = re.compile(r'^\s*\*?\s*text\s*=\s*auto', re.MULTILINE)
EOL_LINE_RE = re.compile(r'^\s*\*.*eol\s*=\s*lf', re.MULTILINE)

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


COUNT_RE = re.compile(r'(?P<count>\d+)\s+skills?\b', re.I)

def find_count_drift(root: Path, docs: dict[str, str]) -> list[dict]:
    """Detect drift where README says 'N skills' but filesystem has M skill dirs.
    Looks for '<N> skills' patterns in docs and compares to count of immediate
    subdirectories under <root>/skills. Returns drifts where doc count != actual.
    One entry per file (first mismatched count per file).

    Precision: skips sub-counts like "32 skills ship a scripts/_common.py"
    (a subset, not the collection total).
    """
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    try:
        actual = sum(1 for p in skills_dir.iterdir() if p.is_dir())
    except Exception:
        return []
    if actual == 0:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in COUNT_RE.finditer(content):
            try:
                doc_count = int(m.group("count"))
            except ValueError:
                continue
            # Skip subset mentions: "32 skills ship/use/with/via" — not total count
            after = content[m.end():m.end()+30].lower()
            if after.lstrip().startswith(("ship", "use ", "with ", "via ", "for ")):
                continue
            # Also skip if the surrounding sentence is about a subset feature
            # e.g. "32 skills ship a `scripts/_common.py`"
            window = content[max(0, m.start()-20):m.end()+40].lower()
            if "ship a" in window and "scripts" in window:
                continue
            if doc_count != actual:
                drifts.append({"file": fname, "doc_count": str(doc_count), "actual_count": actual, "pos": m.start()})
                break
    return drifts


ACTIONS_NODE24_FIX = {
    "actions/checkout": {"deprecated": "v4", "fixed": "v5"},
    "actions/setup-node": {"deprecated": "v4", "fixed": "v5"},
    "actions/configure-pages": {"deprecated": "v5", "fixed": "v6"},
    "actions/deploy-pages": {"deprecated": "v4", "fixed": "v5"},
    "pnpm/action-setup": {"deprecated": "v4", "fixed": "v5"},
}
ACTIONS_RE = re.compile(r'uses:\s*(?P<action>[A-Za-z0-9_.\-\/]+)\s*@\s*(?P<ver>v\d+(?:\.\d+)*)', re.I)

def find_actions_node_drift(root: Path) -> list[dict]:
    """Detect GitHub Actions still pinned to deprecated Node 20 runtime versions.
    Scans .github/workflows/*.yml/.yaml for known actions where the pinned
    major version still uses node20 and a node24 fixed version exists.
    Returns list of {file, action, current, suggested, pos}.
    """
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    drifts = []
    for wf in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        try:
            text = wf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(wf.relative_to(root))
        for m in ACTIONS_RE.finditer(text):
            action = m.group("action")
            ver = m.group("ver").lower()
            # normalize v4.1.0 -> v4
            major = ver.split(".")[0]
            fix = ACTIONS_NODE24_FIX.get(action)
            if not fix:
                continue
            dep_major = fix["deprecated"].lower()
            if major == dep_major:
                drifts.append({"file": rel, "action": action, "current": ver, "suggested": fix["fixed"], "pos": m.start()})
    return drifts


def find_lineending_drift(root: Path) -> list[dict]:
    """Detect missing CRLF-safe .gitattributes.

    A repo that ships text source but lacks `* text=auto eol=lf` in
    .gitattributes can check out with CRLF working-tree bytes on Windows
    (core.autocrlf=true) while the index stores LF -- silently breaking
    byte-exact checks. Returns a drift if .gitattributes is absent or does
    not normalize line endings.
    """
    ga = root / ".gitattributes"
    if not ga.exists():
        return [{
            "file": ".gitattributes",
            "kind": "lineending",
            "detail": "missing .gitattributes with `* text=auto eol=lf`",
        }]
    text = ga.read_text(encoding="utf-8", errors="replace")
    if not (EOL_ATTR_RE.search(text) and EOL_LINE_RE.search(text)):
        return [{
            "file": ".gitattributes",
            "kind": "lineending",
            "detail": ".gitattributes does not set `* text=auto eol=lf`",
        }]
    return []

# ---------------------------------------------------------------------------
# External resource drift: delivered HTML fetches third-party hosts
# ---------------------------------------------------------------------------
# Inspired by tt-a1i/archify#242: delivered HTML links fonts.googleapis.com so
# every viewer's browser makes a third-party request and offline/air-gapped
# viewers silently lose typography. The SVG export is already clean (local()
# fallback), so the HTML path is fixable.
EXTERNAL_CDN_RE = re.compile(
    r'https?://(?P<host>fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)[^\s\"\'<>]*',
    re.I,
)

def find_external_resource_drift(root: Path) -> list[dict]:
    """Detect delivered HTML that fetches external CDN hosts.

    Scans archify-style delivered HTML (archify/assets/template.html and
    examples/*.html) for third-party CDN links. A self-contained artifact
    should not require a network request to render as designed; offline it
    silently degrades. Reported as informational (non-blocking) by default.

    Returns list of {file, kind, host, url, pos, detail}.
    """
    candidates: list[Path] = []
    template = root / "archify" / "assets" / "template.html"
    if template.exists():
        candidates.append(template)
    alt_template = root / "assets" / "template.html"
    if alt_template.exists() and alt_template not in candidates:
        candidates.append(alt_template)
    for pattern in ["examples/*.html", "archify/examples/*.html", "docs/gallery/artifacts/*.html"]:
        candidates.extend(root.glob(pattern))
    drifts: list[dict] = []
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(path.relative_to(root))
        for m in EXTERNAL_CDN_RE.finditer(text):
            drifts.append({
                "file": rel,
                "kind": "external_resource",
                "host": m.group("host").lower(),
                "url": m.group(0),
                "pos": m.start(),
                "detail": f"external CDN {m.group('host')} — delivered HTML fetches third-party host, breaks offline rendering (cf. archify#242)",
            })
            break  # one per file
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
            text = ga.read_text(encoding="utf-8", errors="replace")
            if "text=auto eol=lf" not in text:
                text = text.rstrip("\n") + "\n\n# Normalize line endings (added by driftcheck --fix)\n" + needed
                ga.write_text(text, encoding="utf-8")
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
    count_drifts = find_count_drift(root, docs)
    actions_drifts = find_actions_node_drift(root)
    lineending_drifts = find_lineending_drift(root)
    external_resource_drifts = find_external_resource_drift(root)
    
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
        "count_drifts": count_drifts,
        "actions_drifts": actions_drifts,
        "lineending_drifts": lineending_drifts,
        "external_resource_drifts": external_resource_drifts,
    }