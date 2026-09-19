"""External resource drift detection: HTML files referencing external CDNs."""
from __future__ import annotations
import re
from pathlib import Path

# Detects external CDN dependencies in HTML files — fonts.googleapis.com,
# cdn.jsdelivr.net, unpkg.com, cdnjs.cloudflare.com, etc.
# A self-contained artifact should not require a network request to render
# as designed; offline it silently degrades.
EXTERNAL_CDN_RE = re.compile(
    r'https?://(?P<host>fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com|cdn\.rawgit\.com|maxcdn\.bootstrapcdn\.com|code\.jquery\.com)[^\s"\'<>]*',
    re.I,
)

# Directories to skip during recursive HTML scan
SKIP_DIRS = frozenset({
    "node_modules", "vendor", ".git", "build", "dist", "__pycache__",
    ".venv", "venv", ".tox", ".eggs", "htmlcov", ".next", ".nuxt",
    "out", "target", "bower_components", ".cache", ".gradle", ".m2",
})


def find_external_resource_drift(root: Path) -> list[dict]:
    """Detect HTML files that reference external CDN hosts.

    Scans all *.html files in the repository (excluding build/vendor
    directories) for third-party CDN links. A self-contained artifact
    should not require a network request to render as designed; offline
    it silently degrades. Reported as informational (non-blocking) by default.

    Returns list of {file, kind, host, url, pos, detail}.
    """
    drifts: list[dict] = []

    for html_path in _iter_html_files(root):
        try:
            text = html_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = html_path.relative_to(root).as_posix()
        for m in EXTERNAL_CDN_RE.finditer(text):
            drifts.append({
                "file": rel,
                "kind": "external_resource",
                "host": m.group("host").lower(),
                "url": m.group(0),
                "pos": m.start(),
                "detail": (
                    f"external CDN {m.group('host')} — HTML fetches "
                    f"third-party host, breaks offline rendering"
                ),
            })
            break  # one per file

    return drifts


def _iter_html_files(root: Path):
    """Yield all .html files under root, skipping build/vendor dirs."""
    for path in root.rglob("*.html"):
        # Skip files in excluded directories
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        if path.is_file():
            yield path
