"""External resource drift detection: delivered HTML fetches third-party hosts."""
from __future__ import annotations
import re
from pathlib import Path

# Inspired by tt-a1i/archify#242: delivered HTML links fonts.googleapis.com so
# every viewer's browser makes a third-party request and offline/air-gapped
# viewers silently lose typography. The SVG export is already clean (local()
# fallback), so the HTML path is fixable.
EXTERNAL_CDN_RE = re.compile(
    r'https?://(?P<host>fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)[^\s"\'<>]*',
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
