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




# ---------------------------------------------------------------------------
# .NET / C# drift: .csproj <TargetFramework> vs README mentions
# DOTNET_RE matches: ".NET 8.0" / "using .NET 7.0" / "targets .NET 9.0" etc.
DOTNET_TF_RE = re.compile(r'<TargetFrameworks?\s*>\s*(?P<tf>[^<]+)</TargetFrameworks?>', re.I)
DOTNET_DOC_RE = re.compile(r'\.NET\s+(?:Core\s+|Runtime\s+|SDK\s+)?(?P<ver>[0-9]+(?:\.[0-9]+)?)', re.I)

def parse_dotnet_tfm(csproj_text: str) -> str | None:
    """Parse .NET TargetFramework from a .csproj file. Returns major.minor (e.g., '8.0')."""
    m = DOTNET_TF_RE.search(csproj_text)
    if not m:
        return None
    tfm = m.group("tf").strip()
    first = tfm.split(";")[0].strip()  # multi-targeting → first TFM
    if first.startswith("net"):
        return first[3:]  # "net8.0" → "8.0"
    return None

def find_dotnet_drift(csproj_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect .NET version drift between .csproj <TargetFramework> and docs mentions.

    Returns list of {file, doc_version, csproj_version, pos}.
    Only flags when doc version differs from the csproj TFM.
    """
    if not csproj_files:
        return []
    versions = set()
    for text in csproj_files.values():
        v = parse_dotnet_tfm(text)
        if v:
            versions.add(v)
    if not versions:
        return []
    csproj_ver = max(versions, key=lambda v: tuple(int(x) for x in v.split(".")))
    drifts = []
    for fname, doc_content in docs.items():
        for m in DOTNET_DOC_RE.finditer(doc_content):
            dv = m.group("ver")
            if dv != csproj_ver:
                drifts.append({"file": fname, "doc_version": dv, "csproj_version": csproj_ver, "pos": m.start()})
                break
    return drifts


# ---------------------------------------------------------------------------
# Ruby drift: Gemfile ruby version vs README mentions
# ---------------------------------------------------------------------------
GEMFILE_RUBY_RE = re.compile(r'^\s*ruby\s+["\'](?P<ver>\d+\.\d+(?:\.\d+)?)["\']', re.MULTILINE)
RUBY_DOC_RE = re.compile(
    r'(?:install|use|require[sd]?|minimum|supports?|version|with|needs)\s+Ruby\s+(?P<ver>\d+\.\d+(?:\.\d+)?)|(?<!\w)Ruby\s+(?P<ver2>\d+\.\d+(?:\.\d+)?)(?=\s|$|,|\.|;)',
    re.I
)


def parse_gemfile_ruby_version(text: str) -> str | None:
    """Parse ruby version from Gemfile. Returns major.minor (e.g., '3.2')."""
    m = GEMFILE_RUBY_RE.search(text)
    return m.group("ver") if m else None


def find_ruby_drift(gemfile_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Ruby version drift between Gemfile and README mentions.

    Returns list of {file, doc_version, gemfile_version, pos}.
    Only flags when the doc's Ruby major.minor doesn't match Gemfile.
    """
    if not gemfile_text:
        return []
    gv = parse_gemfile_ruby_version(gemfile_text)
    if not gv:
        return []
    gv_major_minor = ".".join(gv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in RUBY_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != gv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "gemfile_version": gv,
                    "pos": m.start(),
                })
                break
    return drifts


# ---------------------------------------------------------------------------
# PHP/Composer drift: composer.json require.php vs README mentions
# ---------------------------------------------------------------------------
COMPOSER_PHP_RE = re.compile(r'"php"\s*:\s*"(?P<ver>[^\"]+)"')
PHP_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)\s+PHP\s+(?P<ver>\d+(?:\.\d+)?)|(?<!\w)PHP\s+(?P<ver2>\d+(?:\.\d+)?)(?=\s|$|,|\\.|;)',
    re.I
)


def parse_composer_php_version(text: str) -> str | None:
    """Parse PHP version from composer.json require.php. Returns major.minor (e.g., '8.2')."""
    m = COMPOSER_PHP_RE.search(text)
    if not m:
        return None
    ver = m.group("ver")
    # Handle ranges like "^8.2", ">=8.2", "~8.2", "8.2.*"
    ver = re.sub(r'[\^~>=<]+', '', ver).strip()
    ver = ver.replace('.*', '')
    parts = ver.split('.')
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return ver


def find_php_drift(composer_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect PHP version drift between composer.json and README mentions.

    Returns list of {file, doc_version, composer_version, pos}.
    Only flags when the doc's PHP major.minor doesn't match composer.json.
    """
    if not composer_text:
        return []
    cv = parse_composer_php_version(composer_text)
    if not cv:
        return []
    cv_major_minor = ".".join(cv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in PHP_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != cv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "composer_version": cv,
                    "pos": m.start(),
                })
                break
    return drifts


# ---------------------------------------------------------------------------
# Bun drift: package.json engines.bun vs README mentions
# ---------------------------------------------------------------------------
BUN_ENGINES_RE = re.compile(r'"bun"\s*:\s*"(?P<ver>[^\"]+)"')
BUN_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)\s+Bun\s+(?P<ver>\d+(?:\.\d+)?)|(?<!\w)Bun\s+(?P<ver2>\d+(?:\.\d+)?)(?=\s|$|,|\\.|;)',
    re.I
)


def parse_bun_version_from_package(text: str) -> str | None:
    """Parse Bun version from package.json engines.bun. Returns major.minor (e.g., '1.0')."""
    try:
        data = json.loads(text)
        bun_ver = data.get("engines", {}).get("bun", "")
        if not bun_ver:
            return None
        # Handle ranges like ">=1.0", "^1.0", "~1.0"
        bun_ver = re.sub(r'[\^~>=<]+', '', bun_ver).strip()
        parts = bun_ver.split('.')
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return bun_ver
    except Exception:
        return None


def find_bun_drift(package_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Bun version drift between package.json engines.bun and README mentions.

    Returns list of {file, doc_version, package_version, pos}.
    Only flags when the doc's Bun major.minor doesn't match package.json.
    """
    if not package_text:
        return []
    bv = parse_bun_version_from_package(package_text)
    if not bv:
        return []
    bv_major_minor = ".".join(bv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in BUN_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != bv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "package_version": bv,
                    "pos": m.start(),
                })
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
    
    Only fires when the repo has source files (to avoid noise on empty dirs).
    """
    # Check if repo has any source files that would need line ending normalization
    source_patterns = [
        "*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.rs", "*.go", "*.java",
        "*.kt", "*.kts", "*.c", "*.cpp", "*.h", "*.hpp", "*.rb", "*.php",
        "*.cs", "*.fs", "*.swift", "*.m", "*.mm", "*.scala", "*.clj",
        "*.sh", "*.bash", "*.zsh", "*.fish", "*.ps1", "*.bat", "*.cmd",
        "*.xml", "*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.cfg",
        "*.conf", "*.config", "*.properties", "*.gradle", "*.sbt",
        "Makefile", "Dockerfile", "*.md", "*.rst", "*.txt",
    ]
    has_source = False
    for pattern in source_patterns:
        if list(root.glob(pattern)):
            has_source = True
            break
    if not has_source:
        # Check common subdirectories
        for subdir in ["src", "lib", "app", "test", "tests", "scripts", "bin", "pkg", "cmd"]:
            subpath = root / subdir
            if subpath.exists():
                for pattern in source_patterns:
                    if list(subpath.glob(pattern)):
                        has_source = True
                        break
            if has_source:
                break
    
    if not has_source:
        return []  # Empty repo or no source files — skip lineending check

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

# ---------------------------------------------------------------------------
# Docker drift: Dockerfile FROM <image>:<tag> vs README mentions
# ---------------------------------------------------------------------------
DOCKER_FROM_RE = re.compile(r'^FROM\s+(?:--\S+\s+)?(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)', re.MULTILINE | re.I)
DOCKER_TAG_RE = re.compile(r'(?:Docker|image)\s+(?P<image>[\w.\-]+):(?P<tag>[\w.\-]+)|(?:Docker|image)\s+(?:version|tag)?\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_dockerfile_from(text: str) -> dict[str, str]:
    """Return {image: tag} map of FROM instructions in a Dockerfile."""
    result = {}
    for m in DOCKER_FROM_RE.finditer(text):
        result[m.group("image").lower()] = m.group("tag")
    return result

def find_docker_drift(dockerfiles: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Dockerfile FROM tags and README mentions.

    Scans docs for patterns like 'node:24' or 'Docker node 22' and compares
    to the actual FROM tag in the Dockerfile. Returns drifts where the doc
    mentions a different version than what the Dockerfile pins.
    """
    # Collect all FROM tags across dockerfiles
    all_from: dict[str, str] = {}
    for fname, content in dockerfiles.items():
        for image, tag in parse_dockerfile_from(content).items():
            all_from[image] = tag

    if not all_from:
        return []

    def tags_match(doc_tag: str, from_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == from_tag:
            return True
        # '24' matches '24-slim', '24-alpine', etc.
        if from_tag.startswith(doc_tag + "-"):
            return True
        # '24-slim' matches '24'
        if doc_tag.startswith(from_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in DOCKER_TAG_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            # Match by image name (node, python, golang, etc.)
            for from_img, from_tag in all_from.items():
                if img and img not in from_img and from_img not in img:
                    continue
                if not tags_match(tag, from_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or from_img}:{tag}",
                        "dockerfile_image": f"{from_img}:{from_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# Java/Gradle drift: build.gradle sourceCompatibility vs README
# ---------------------------------------------------------------------------
GRADLE_JAVA_RE = re.compile(r'sourceCompatibility\s*=\s*["\']?(?P<ver>\d+(?:\.\d+)?)["\']?|JavaVersion\.VERSION_(?P<ver2>_\d+|(?:\d+))', re.I)
GRADLE_KOTLIN_RE = re.compile(r'jvmTarget\s*=\s*["\']?(?P<ver>\d+(?:\.\d+)?)["\']?', re.I)
JAVA_DOC_RE = re.compile(r'(?:Java|JDK|JRE)\s+(?P<ver>\d+(?:\.\d+)?)', re.I)

def parse_gradle_java_version(text: str) -> str | None:
    """Parse Java version from build.gradle sourceCompatibility or jvmTarget."""
    m = GRADLE_JAVA_RE.search(text)
    if m:
        v = m.group("ver") or m.group("ver2")
        if v:
            return v.replace("_", "")
    m = GRADLE_KOTLIN_RE.search(text)
    if m:
        return m.group("ver")
    return None

def find_java_drift(gradle_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between build.gradle Java version and README mentions."""
    jv = parse_gradle_java_version(gradle_text)
    if not jv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in JAVA_DOC_RE.finditer(content):
            dv = m.group("ver")
            # Normalize: "17.0.1" -> "17" for comparison with sourceCompatibility
            dv_major = dv.split(".")[0]
            jv_major = jv.split(".")[0]
            if dv_major != jv_major:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "gradle_version": jv,
                    "pos": m.start(),
                })
                break
    return drifts


# ---------------------------------------------------------------------------
# Maven drift: pom.xml version vs README
# ---------------------------------------------------------------------------
MAVEN_VER_RE = re.compile(r'<(?:java\.version|maven\.compiler\.source|maven\.compiler\.target|release)>(?P<ver>\d+(?:\.\d+)?)</')
MAVEN_DOC_RE = re.compile(r'(?:Java|JDK|JRE|requires)\s+(?P<ver>\d+(?:\.\d+)?)', re.I)

def parse_maven_java_version(text: str) -> str | None:
    """Parse Java version from pom.xml java.version or maven.compiler.source."""
    m = MAVEN_VER_RE.search(text)
    return m.group("ver") if m else None

def find_maven_drift(pom_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between pom.xml Java version and README mentions."""
    mv = parse_maven_java_version(pom_text)
    if not mv:
        return []
    drifts = []
    for fname, content in docs.items():
        for m in MAVEN_DOC_RE.finditer(content):
            dv = m.group("ver")
            dv_major = dv.split(".")[0]
            mv_major = mv.split(".")[0]
            if dv_major != mv_major:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "maven_version": mv,
                    "pos": m.start(),
                })
                break
    return drifts


# ---------------------------------------------------------------------------
# Terraform drift: versions.tf provider versions vs README
# ---------------------------------------------------------------------------
TERRAFORM_PROVIDER_RE = re.compile(r'required_providers\s*=?\s*\{[^}]*source\s*=\s*"(?P<source>[^"]+)"[^}]*version\s*=\s*"(?P<ver>[^"]+)"', re.S)
TERRAFORM_VER_RE = re.compile(r'(?:provider|terraform|version)\s+"?(?P<ver>\d+\.\d+(?:\.\d+)?)"?', re.I)

def parse_terraform_provider_versions(text: str) -> dict[str, str]:
    """Return {source: version} map of required_providers in versions.tf."""
    result = {}
    for m in TERRAFORM_PROVIDER_RE.finditer(text):
        result[m.group("source")] = m.group("ver")
    return result

def find_terraform_drift(terraform_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Terraform provider versions and README mentions."""
    all_providers: dict[str, str] = {}
    for fname, content in terraform_files.items():
        for source, ver in parse_terraform_provider_versions(content).items():
            all_providers[source] = ver

    if not all_providers:
        return []

    drifts = []
    for fname, content in docs.items():
        for m in TERRAFORM_VER_RE.finditer(content):
            ver = m.group("ver")
            # Check if this version matches any provider version
            for source, tf_ver in all_providers.items():
                if ver != tf_ver and ver.split(".")[:2] == tf_ver.split(".")[:2]:
                    # Same major.minor, different patch — skip
                    continue
                if ver != tf_ver:
                    drifts.append({
                        "file": fname,
                        "doc_version": ver,
                        "terraform_version": tf_ver,
                        "provider": source,
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# CircleCI drift: .circleci/config.yml docker image tags vs README
# ---------------------------------------------------------------------------
CIRCLECI_IMAGE_RE = re.compile(r'image:\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)')
CIRCLECI_VER_RE = re.compile(r'(?:image|docker|version)\s+(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_circleci_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of docker images in CircleCI config."""
    result = {}
    for m in CIRCLECI_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result

def find_circleci_drift(circleci_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between CircleCI docker image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in circleci_files.items():
        for image, tag in parse_circleci_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, ci_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == ci_tag:
            return True
        if ci_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(ci_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in CIRCLECI_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for ci_img, ci_tag in all_images.items():
                if img and img not in ci_img and ci_img not in img:
                    continue
                if not tags_match(tag, ci_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or ci_img}:{tag}",
                        "circleci_image": f"{ci_img}:{ci_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# GitLab CI drift: .gitlab-ci.yml image tags vs README
# ---------------------------------------------------------------------------
GITLAB_IMAGE_RE = re.compile(r'image:\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)')
GITLAB_VER_RE = re.compile(r'(?:image|docker|version)\s+(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_gitlab_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of docker images in GitLab CI config."""
    result = {}
    for m in GITLAB_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result

def find_gitlab_drift(gitlab_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between GitLab CI docker image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in gitlab_files.items():
        for image, tag in parse_gitlab_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, ci_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == ci_tag:
            return True
        if ci_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(ci_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in GITLAB_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for ci_img, ci_tag in all_images.items():
                if img and img not in ci_img and ci_img not in img:
                    continue
                if not tags_match(tag, ci_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or ci_img}:{tag}",
                        "gitlab_image": f"{ci_img}:{ci_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# GitHub Actions version drift: detect outdated action versions in workflows
# ---------------------------------------------------------------------------
# Known latest versions for popular actions (update periodically)
GH_ACTIONS_LATEST = {
    "actions/checkout": "v5",
    "actions/setup-node": "v5",
    "actions/setup-python": "v6",
    "actions/setup-java": "v5",
    "actions/setup-go": "v6",
    "actions/cache": "v6",
    "actions/upload-artifact": "v5",
    "actions/download-artifact": "v5",
    "pnpm/action-setup": "v5",
    "actions/configure-pages": "v6",
    "actions/deploy-pages": "v6",
    "actions/stale": "v10",
    "actions/labeler": "v6",
    "actions/dependency-review-action": "v5",
    "github/codeql-action/init": "v4",
    "github/codeql-action/analyze": "v4",
    "codecov/codecov-action": "v5",
    "dorny/test-reporter": "v2",
    "codecov/codecov-action": "v5",
}

GH_ACTIONS_RE = re.compile(r'uses:\s*(?P<action>[A-Za-z0-9_.\-\/]+)\s*@(?P<ver>v\d+(?:\.\d+)*)', re.I)

def find_gh_actions_version_drift(root: Path) -> list[dict]:
    """Detect outdated GitHub Actions versions in .github/workflows/*.yml/.yaml.
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
        for m in GH_ACTIONS_RE.finditer(text):
            action = m.group("action")
            ver = m.group("ver").lower()
            latest = GH_ACTIONS_LATEST.get(action)
            if not latest:
                continue
            if ver != latest:
                drifts.append({
                    "file": rel,
                    "action": action,
                    "current": ver,
                    "suggested": latest,
                    "pos": m.start(),
                })
    return drifts


# ---------------------------------------------------------------------------
# Kubernetes drift: image tags in manifests vs README
# ---------------------------------------------------------------------------
K8S_IMAGE_RE = re.compile(r'image:\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)')
K8S_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_k8s_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of container images in K8s manifests."""
    result = {}
    for m in K8S_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result

def find_k8s_drift(k8s_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between K8s image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in k8s_files.items():
        for image, tag in parse_k8s_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, k8s_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == k8s_tag:
            return True
        if k8s_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(k8s_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in K8S_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for k8s_img, k8s_tag in all_images.items():
                if img and img not in k8s_img and k8s_img not in img:
                    continue
                if not tags_match(tag, k8s_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or k8s_img}:{tag}",
                        "k8s_image": f"{k8s_img}:{k8s_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# Helm drift: Chart.yaml/values.yaml image tags vs README
# ---------------------------------------------------------------------------
HELM_IMAGE_RE = re.compile(r'(?:repository|image):\s*["\']?(?P<image>[\w.\-/]+)["\']?\s*\n\s*(?:tag|version):\s*["\']?(?P<tag>[\w.\-]+)["\']?', re.I)
HELM_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_helm_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of images in Helm Chart.yaml/values.yaml."""
    result = {}
    for m in HELM_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result

def find_helm_drift(helm_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Helm chart image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in helm_files.items():
        for image, tag in parse_helm_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, helm_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == helm_tag:
            return True
        if helm_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(helm_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in HELM_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for helm_img, helm_tag in all_images.items():
                if img and img not in helm_img and helm_img not in img:
                    continue
                if not tags_match(tag, helm_tag):
                    drifts.append({
                        "file": fname,
                        "doc_version": f"{img or helm_img}:{tag}",
                        "helm_image": f"{helm_img}:{helm_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# Docker Compose drift: docker-compose.yml image tags vs README
# ---------------------------------------------------------------------------
DC_IMAGE_RE = re.compile(r'^\s{4,}(?:image:\s*)(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)', re.MULTILINE)
DC_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)

def parse_docker_compose_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of images in docker-compose.yml / compose.yaml."""
    result = {}
    for m in DC_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result

def find_docker_compose_drift(dc_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between docker-compose.yml image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in dc_files.items():
        for image, tag in parse_docker_compose_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, dc_tag: str) -> bool:
        if doc_tag == dc_tag:
            return True
        if dc_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(dc_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in DC_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for dc_img, dc_tag in all_images.items():
                if img and img not in dc_img and dc_img not in img:
                    continue
                if not tags_match(tag, dc_tag):
                    drifts.append({
                        "file": fname,
                        "doc_version": f"{img or dc_img}:{tag}",
                        "compose_image": f"{dc_img}:{dc_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts


# ---------------------------------------------------------------------------
# Dependabot drift: ecosystems used vs dependabot.yml coverage
# ---------------------------------------------------------------------------
DEPENDABOT_RE = re.compile(r'package-ecosystem:\s*"(?P<ecosystem>[^"]+)"', re.I)

# Map of ecosystem -> files that indicate usage
ECOSYSTEM_FILES = {
    "npm": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
    "pip": ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg"],
    "gomod": ["go.mod"],
    "cargo": ["Cargo.toml"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "docker": ["Dockerfile", "docker-compose.yml", "compose.yaml"],
    "github-actions": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "bundler": ["Gemfile"],
    "composer": ["composer.json"],
    "mix": ["mix.exs"],
    "nuget": ["*.csproj", "*.sln"],
    "pub": ["pubspec.yaml"],
}

def find_dependabot_drift(root: Path) -> list[dict]:
    """Detect ecosystems used by the repo but not covered by dependabot.yml."""
    # Find which ecosystems are in use
    used_ecosystems = set()
    for eco, patterns in ECOSYSTEM_FILES.items():
        for pattern in patterns:
            if list(root.glob(pattern)):
                used_ecosystems.add(eco)
                break

    if not used_ecosystems:
        return []

    # Check dependabot.yml
    dependabot_path = root / ".github" / "dependabot.yml"
    if not dependabot_path.exists():
        dependabot_path = root / ".github" / "dependabot.yaml"

    if not dependabot_path.exists():
        # No dependabot at all — report all used ecosystems as missing
        return [{
            "file": ".github/dependabot.yml",
            "kind": "dependabot_missing",
            "ecosystems": sorted(used_ecosystems),
            "detail": f"dependabot.yml not found but ecosystems in use: {', '.join(sorted(used_ecosystems))}",
        }]

    # Parse existing dependabot config
    try:
        text = dependabot_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    configured = set()
    for m in DEPENDABOT_RE.finditer(text):
        configured.add(m.group("ecosystem").lower())

    missing = used_ecosystems - configured
    if not missing:
        return []

    return [{
        "file": ".github/dependabot.yml",
        "kind": "dependabot_incomplete",
        "ecosystems": sorted(missing),
        "configured": sorted(configured),
        "detail": f"dependabot.yml missing ecosystems: {', '.join(sorted(missing))} (configured: {', '.join(sorted(configured))})",
    }]


# ---------------------------------------------------------------------------
# CI OS drift: detect deprecated GitHub Actions runners
# ---------------------------------------------------------------------------
CI_OS_DEPRECATED = {
    "ubuntu-18.04": "ubuntu-22.04",
    "ubuntu-20.04": "ubuntu-22.04",
    "macos-10.15": "macos-13",
    "macos-11": "macos-13",
    "windows-2016": "windows-2022",
    "windows-2019": "windows-2022",
}

CI_OS_RE = re.compile(r'runs-on:\s*(?P<runner>[^\s#]+)', re.I)

def find_ci_os_drift(root: Path) -> list[dict]:
    """Detect deprecated CI runners in GitHub Actions workflows."""
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
        for m in CI_OS_RE.finditer(text):
            runner = m.group("runner").lower()
            if runner in CI_OS_DEPRECATED:
                drifts.append({
                    "file": rel,
                    "runner": runner,
                    "suggested": CI_OS_DEPRECATED[runner],
                    "pos": m.start(),
                    "detail": f"deprecated runner {runner} → {CI_OS_DEPRECATED[runner]}",
                })
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
    
    # Dockerfiles
    dockerfiles = {}
    for pattern in ["Dockerfile", "Dockerfile.*", "docker/Dockerfile", "docker/Dockerfile.*"]:
        for p in root.glob(pattern):
            if p.is_file():
                dockerfiles[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Gradle build files
    gradle_files = {}
    for pattern in ["build.gradle", "build.gradle.kts", "gradle/build.gradle", "gradle/build.gradle.kts"]:
        for p in root.glob(pattern):
            if p.is_file():
                gradle_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Maven pom.xml files
    maven_files = {}
    for pattern in ["pom.xml", "maven/pom.xml"]:
        for p in root.glob(pattern):
            if p.is_file():
                maven_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Terraform files
    terraform_files = {}
    for pattern in ["versions.tf", "*.tf", "terraform/*.tf"]:
        for p in root.glob(pattern):
            if p.is_file():
                terraform_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # CircleCI config files
    circleci_files = {}
    for pattern in [".circleci/config.yml", ".circleci/config.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                circleci_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # GitLab CI config files
    gitlab_files = {}
    for pattern in [".gitlab-ci.yml", ".gitlab-ci.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                gitlab_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Kubernetes manifests
    k8s_files = {}
    for pattern in ["k8s/**/*.yaml", "k8s/**/*.yml", "kubernetes/**/*.yaml", "kubernetes/**/*.yml", "deploy/**/*.yaml", "deploy/**/*.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                k8s_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    # Docker Compose files
    dc_files = {}
    for pattern in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "docker/docker-compose.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                dc_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")


    # Helm chart files
    helm_files = {}
    for pattern in ["Chart.yaml", "charts/**/Chart.yaml", "values.yaml", "charts/**/values.yaml", "charts/**/values.*.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                helm_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    # Ruby project files (Gemfile)
    gemfile_path = root / "Gemfile"
    gemfile_text = gemfile_path.read_text(encoding="utf-8", errors="replace") if gemfile_path.exists() else ""

    # PHP/Composer project files
    composer_path = root / "composer.json"
    composer_text = composer_path.read_text(encoding="utf-8", errors="replace") if composer_path.exists() else ""

    # .NET / C# project files
    csproj_files = {}
    for pattern in ["*.csproj", "**/*.csproj", "src/**/*.csproj", "tests/**/*.csproj"]:
        for p in root.glob(pattern):
            if p.is_file():
                csproj_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    
    rust_drifts = find_rust_drift(toolchain_text, docs)
    rust_drifts_multi = find_rust_drift_multi(toolchain_text, cargo_text, docs)
    node_drifts = find_node_drift(package_text, docs)
    bun_drifts = find_bun_drift(package_text, docs)
    python_drifts = find_python_drift(pyproject_text, docs)
    go_drifts = find_go_drift(gomod_text, docs)
    count_drifts = find_count_drift(root, docs)
    actions_drifts = find_actions_node_drift(root)
    lineending_drifts = find_lineending_drift(root)
    external_resource_drifts = find_external_resource_drift(root)
    docker_drifts = find_docker_drift(dockerfiles, docs)
    java_drifts = find_java_drift("\n".join(gradle_files.values()), docs)
    maven_drifts = find_maven_drift("\n".join(maven_files.values()), docs)
    terraform_drifts = find_terraform_drift(terraform_files, docs)
    circleci_drifts = find_circleci_drift(circleci_files, docs)
    gitlab_drifts = find_gitlab_drift(gitlab_files, docs)
    k8s_drifts = find_k8s_drift(k8s_files, docs)
    helm_drifts = find_helm_drift(helm_files, docs)
    dc_drifts = find_docker_compose_drift(dc_files, docs)
    dependabot_drifts = find_dependabot_drift(root)
    dotnet_drifts = find_dotnet_drift(csproj_files, docs)
    ruby_drifts = find_ruby_drift(gemfile_text, docs)
    php_drifts = find_php_drift(composer_text, docs)
    
    return {
        "toolchain_version": parse_toolchain_version(toolchain_text),
        "cargo_rust_version": parse_cargo_rust_version(cargo_text),
        "package_node": parse_node_version_from_package(package_text),
        "pyproject_python": parse_python_version_from_pyproject(pyproject_text),
        "gomod_version": parse_go_version_from_gomod(gomod_text),
        "drifts": rust_drifts,
        "rust_drifts": rust_drifts_multi,
        "node_drifts": node_drifts,
        "bun_drifts": bun_drifts,
        "python_drifts": python_drifts,
        "go_drifts": go_drifts,
        "count_drifts": count_drifts,
        "actions_drifts": actions_drifts,
        "gh_actions_version_drifts": find_gh_actions_version_drift(root),
        "lineending_drifts": lineending_drifts,
        "external_resource_drifts": external_resource_drifts,
        "docker_drifts": docker_drifts,
        "java_drifts": java_drifts,
        "maven_drifts": maven_drifts,
        "terraform_drifts": terraform_drifts,
        "circleci_drifts": circleci_drifts,
        "gitlab_drifts": gitlab_drifts,
        "helm_drifts": helm_drifts,
        "dc_drifts": dc_drifts,
        "dependabot_drifts": dependabot_drifts,
        "ci_os_drifts": find_ci_os_drift(root),
        "k8s_drifts": k8s_drifts,
        "dotnet_drifts": dotnet_drifts,
        "ruby_drifts": ruby_drifts,
        "php_drifts": php_drifts,
    }