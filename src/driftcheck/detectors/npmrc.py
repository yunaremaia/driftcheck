"""NPMRC drift detection: .npmrc registry vs README mentions."""
from __future__ import annotations
import re

# Match any URL in docs
URL_RE = re.compile(
    r'(?P<url>https?://[^\s"\']+)',
    re.I,
)


def parse_npmrc_registry(text: str) -> str | None:
    """Return registry URL from .npmrc file."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            if key.strip().lower() == "registry":
                return value.strip().strip('"').strip("'")
    return None


def find_npmrc_drift(
    npmrc_content: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between .npmrc registry and README mentions."""
    if not npmrc_content:
        return []

    registry = parse_npmrc_registry(npmrc_content)
    if not registry:
        return []

    # Extract hostname for comparison
    registry_host = re.sub(r"^https?://", "", registry).rstrip("/")

    drifts = []
    for doc_fname, doc_content in docs.items():
        for m in URL_RE.finditer(doc_content):
            doc_url = m.group("url")
            doc_host = re.sub(r"^https?://", "", doc_url).rstrip("/")
            # Skip if same host (no drift)
            if doc_host == registry_host:
                continue
            # Skip common non-registry URLs (CDNs, docs, etc.)
            skip_domains = {
                "github.com", "docs.npmjs.com", "npmjs.com", "nodejs.org",
                "example.com", "localhost", "127.0.0.1",
            }
            if doc_host in skip_domains or doc_host.endswith(("github.com", "npmjs.com")):
                continue
            drifts.append({
                "file": doc_fname,
                "tool": "npm",
                "doc_registry": doc_url,
                "npmrc_registry": registry,
                "pos": m.start(),
            })

    return drifts
