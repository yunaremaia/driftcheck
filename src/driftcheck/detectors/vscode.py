"""VSCode settings drift detection: .vscode/settings.json vs README.

Detects drift between recommended extensions in VSCode settings and
mentions in README or CONTRIBUTING docs.
"""
from __future__ import annotations
import re

# Match extension mentions in README
EXTENSION_RE = re.compile(
    r'(?:extension|plugin|addon)\s+(?P<id>[\w.-]+\/[\w.-]+|\w+\.\w+)',
    re.I,
)

# Match VSCode recommendations mentions
RECOMMENDATIONS_RE = re.compile(
    r'(?:recommend|suggest)(?:ed|s)?\s+(?:the\s+)?(?:[\w\s]+?\s+)?(?:(?:extension|plugin)\s+)?(?P<ids>[\w.-]+(?:\s*,\s*[\w.-]+)*)',
    re.I,
)


def parse_vscode_extensions(text: str) -> list[str]:
    """Parse extensions from .vscode/settings.json or extensions.json."""
    # Look for extensions.json format
    m = re.search(r'"recommendations"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if m:
        return [e.strip().strip('"').strip("'") for e in m.group(1).split(",") if e.strip()]
    
    # Look for settings.json with recommendations
    m = re.search(r'"recommendations"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if m:
        return [e.strip().strip('"').strip("'") for e in m.group(1).split(",") if e.strip()]
    
    return []


def find_vscode_extensions_drift(
    vscode_content: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between VSCode recommendations and README mentions."""
    if not vscode_content:
        return []
    
    extensions = parse_vscode_extensions(vscode_content)
    if not extensions:
        return []
    
    drifts = []
    for doc_fname, doc_content in docs.items():
        for m in RECOMMENDATIONS_RE.finditer(doc_content):
            mentioned = m.group("ids")
            if mentioned:
                mentioned_ids = [e.strip() for e in mentioned.split(",")]
                for mid in mentioned_ids:
                    if mid and mid not in extensions:
                        drifts.append({
                            "file": doc_fname,
                            "detail": f"README recommends {mid} but not in .vscode/extensions.json",
                            "extension": mid,
                            "recommended_extensions": extensions,
                        })
    
    return drifts
