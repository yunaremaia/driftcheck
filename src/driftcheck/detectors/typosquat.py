"""Typosquat drift detection: package names in lockfiles vs known packages.

Integrates taintrace-style similarity detection into driftcheck's scanning
pipeline. Flags lockfile dependencies whose names are within edit distance 1-2
of a well-known package in the same ecosystem — classic typosquat signature.
"""
from __future__ import annotations
import re
from pathlib import Path

# Lightweight known-package lists per ecosystem (top ~100 from each registry).
# These are intentionally small — driftcheck ships offline and the goal is
# to catch the most common squats, not maintain a full registry mirror.
# For full coverage, users can pipe through taintrace (which has a DB download).

KNOWN_PACKAGES = {
    "pypi": {
        "requests", "numpy", "pandas", "scipy", "matplotlib", "django", "flask",
        "fastapi", "httpx", "aiohttp", "sqlalchemy", "alembic", "pytest", "black",
        "ruff", "mypy", "pylint", "tox", "sphinx", "click", "rich", "pydantic",
        "typer", "jinja2", "markdown", "pillow", "opencv-python", "torch",
        "tensorflow", "transformers", "scikit-learn", "scikit-image", "keras",
        "notebook", "jupyter", "ipykernel", "pip", "setuptools", "wheel", "twine",
        "bumpversion", "virtualenv", "pipenv", "poetry", "hatch", "uv",
        "cryptography", "bcrypt", "passlib", "pyjwt", "authlib", "oauthlib",
        "celery", "redis", "boto3", "botocore", "awscli", "google-cloud-storage",
        "grpcio", "protobuf", "psycopg2", "pymysql", "sqlparse", "arrow",
        "python-dateutil", "pytz", "tzdata", "pyyaml", "toml", "tomli",
        "charset-coder", "idna", "certifi", "urllib3", "chardet", "six",
        "packaging", "importlib-metadata", "zipp", "typing-extensions", "annotated-types",
        "pydantic-core", "email-validator", "dnspython", "httpcore", "anyio",
        "exceptiongroup", "sniffio", "h11", "multidict", "frozenlist",
        "yarl", "async-timeout", "attrs", "aiofiles", "jmespath", "pyasn1",
        "rsa", "pycparser", "cffi", "markupsafe", "itsdangerous", "werkzeug",
        "blinker", "colorama", "platformdirs", "filelock", "distlib",
        "more-itertools", "jaraco-context", "jaraco-functools", "tomli-w",
        "pathspec", "pluggy", "iniconfig", "coverage", "pytest-cov",
    },
    "npm": {
        "react", "react-dom", "vue", "svelte", "next", "nuxt", "express",
        "lodash", "axios", "dotenv", "eslint", "prettier", "typescript", "vite",
        "webpack", "rollup", "esbuild", "turbo", "jest", "mocha", "chai",
        "cypress", "playwright", "tailwindcss", "postcss", "autoprefixer",
        "sass", "less", "stylus", "babel", "rollup", "tsup", "tsdx",
        "date-fns", "dayjs", "luxon", "ramda", "immutable", "rxjs",
        "redux", "zustand", "recoil", "jotai", "mobx", "graphql",
        "apollo-client", "urql", "react-query", "swr", "jose", "bcryptjs",
        "jsonwebtoken", "passport", "multer", "sharp", "socket.io",
        "node-fetch", "got", "undici", "pino", "winston", "chalk",
        "commander", "yargs", "inquirer", "enzyme", "react-testing-library",
        "happy-dom", "vitest", "npm", "pnpm", "yarn", "corepack",
        "typescript-eslint", "@types/react", "@types/node", "@types/lodash",
        "eslint-config-prettier", "eslint-plugin-react", "eslint-plugin-import",
        "prettier-eslint", "stylelint", "commitlint", "husky", "lint-staged",
        "semantic-release", "changesets", "turbo", "nx", "lage",
    },
    "crates": {
        "serde", "serde_json", "serde_derive", "tokio", "rand", "regex",
        "clap", "reqwest", "hyper", "http", "url", "uuid", "chrono",
        "anyhow", "thiserror", "itertools", "futures", "async-trait",
        "tracing", "tracing-subscriber", "log", "env_logger", "dotenv",
        "config", "sqlx", "diesel", "sea-orm", "mongodb", "redis",
        "rayon", "crossbeam", "parking_lot", "once_cell", "lazy_static",
        "bytes", "mio", "tower", "tonic", "prost", "flate2", "tar",
        "walkdir", "glob", "tempfile", "fs2", "memmap", "serde_yaml",
        "toml", "indexmap", "hashbrown", "smallvec", "bitflags",
        "syn", "quote", "proc-macro2", "libc", "winapi", "nix",
        "unicode-ident", "unicode-normalization", "heck", "clap_derive",
    },
}

# Manifest -> ecosystem mapping
MANIFEST_ECOSYSTEM = {
    "requirements.txt": "pypi",
    "pyproject.toml": "pypi",
    "Pipfile": "pypi",
    "setup.py": "pypi",
    "package.json": "npm",
    "Cargo.toml": "crates",
}

# Regexes per ecosystem to extract package names
PYPROJECT_PKG_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9_-]+)', re.MULTILINE,
)
REQUIREMENTS_PKG_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9_-]+)', re.MULTILINE,
)
CARGO_DEP_RE = re.compile(
    r'^(?P<pkg>[A-Za-z0-9_-]+)\s*=', re.MULTILINE,
)


def _levenshtein(s1: str, s2: str) -> int:
    """Calculate edit distance between two strings."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            curr_row.append(min(
                prev_row[j + 1] + 1,
                curr_row[j] + 1,
                prev_row[j] + (c1 != c2),
            ))
        prev_row = curr_row
    return prev_row[-1]


def _find_suspicious_names(name: str, known: set[str]) -> list[str]:
    """Return known packages within edit distance 2 of `name`.
    
    Uses proportional thresholds to avoid false positives on short names:
    - dist=1: only for names with length >= 4
    - dist=2: only for names with length >= 6 (avoids flagging short-name collisions)
    """
    hits = []
    name_lower = name.lower()
    name_len = len(name_lower)
    if name_len < 4:
        return hits
    for known_pkg in known:
        if known_pkg == name_lower:
            continue
        dist = _levenshtein(name_lower, known_pkg)
        if dist == 1 and name_len >= 4:
            hits.append(known_pkg)
        elif dist == 2 and name_len >= 6 and len(known_pkg) >= 6:
            hits.append(known_pkg)
    return hits


def _parse_lockfile(manifest: str, text: str) -> list[str]:
    """Extract dependency names from manifest text."""
    if manifest in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py"):
        pkgs = set()
        for line in text.splitlines():
            m = REQUIREMENTS_PKG_RE.match(line.strip())
            if m:
                pkg = m.group("pkg").lower()
                if pkg not in ("pip", "setuptools", "wheel", "python", "requires"):
                    pkgs.add(pkg)
        return list(pkgs)
    elif manifest == "package.json":
        # Simple regex extraction of dependencies block
        import json
        try:
            data = json.loads(text)
        except Exception:
            return []
        deps = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            block = data.get(section, {})
            if isinstance(block, dict):
                deps.update(block.keys())
        return list(deps)
    elif manifest == "Cargo.toml":
        pkgs = []
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
                in_deps = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_deps = False
                continue
            if in_deps:
                m = CARGO_DEP_RE.match(stripped)
                if m:
                    pkgs.append(m.group("pkg").lower())
        return pkgs
    return []


def find_typosquat_drift(root: Path) -> list[dict]:
    """Detect suspiciously-named dependencies in lockfiles (typosquat pattern).

    For each known manifest (requirements.txt, package.json, Cargo.toml),
    extracts dependency names and compares against a curated list of popular
    packages. Flags any name within edit distance 2 of a known package —
    classic typosquat signature (e.g., `reqeusts` -> `requests`).

    This is a lightweight heuristic. For full registry coverage, use taintrace
    directly (it has a curated database of 100K+ packages per ecosystem).

    Returns list of {file, kind, detail, pos}.
    """
    drifts = []
    for manifest, eco in MANIFEST_ECOSYSTEM.items():
        manifest_path = root / manifest
        if not manifest_path.exists():
            continue
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        known = KNOWN_PACKAGES.get(eco, set())
        if not known:
            continue
        deps = _parse_lockfile(manifest, text)
        for dep in deps:
            similar = _find_suspicious_names(dep, known)
            if similar:
                drifts.append({
                    "file": manifest,
                    "kind": "typosquat_suspect",
                    "detail": (
                        f"suspicious dependency '{dep}' — edit distance <= 2 "
                        f"from known package(s): {', '.join(similar[:3])} "
                        f"(possible typosquat)"
                    ),
                    "pos": 0,
                })
    return drifts
