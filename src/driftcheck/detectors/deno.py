"""Deno drift detection: deno.json / deno.jsonc vs README mentions."""
from __future__ import annotations
import re
import json

DENO_JSON_VER_RE = re.compile(r'"?version"?\s*:\s*"([^"]+)"')
DENO_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)\s+Deno\s+(?P<ver>\d+(?:\.\d+)?)|(?<!\w)Deno\s+(?P<ver2>\d+(?:\.\d+)?)(?=\s|$|,|\.|;)',
    re.I
)

# Field names where version may appear in deno.json
VERSION_FIELDS = ["version", "deno"]


def parse_deno_version(text: str) -> str | None:
    """Parse Deno version from deno.json or deno.jsonc. Returns major.minor (e.g., '2.0')."""
    # Strip comments for deno.jsonc
    clean = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    clean = re.sub(r'/\*.*?\*/', '', clean, flags=re.DOTALL)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Fallback to regex
        m = DENO_JSON_VER_RE.search(text)
        return m.group(1) if m else None

    for field in VERSION_FIELDS:
        v = data.get(field)
        if v:
            if isinstance(v, str):
                m = re.search(r'(\d+(?:\.\d+)?)', v)
                return m.group(1) if m else str(v)
            if isinstance(v, (int, float)):
                return str(v)
    return None


def find_deno_drift(deno_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Deno version drift between deno.json and README mentions.

    Returns list of {file, doc_version, deno_json_version, pos}.
    Only flags when the doc's Deno major.minor doesn't match deno.json.
    """
    if not deno_text:
        return []
    dv_parsed = parse_deno_version(deno_text)
    if not dv_parsed:
        return []
    dv_parts = dv_parsed.split(".")
    if len(dv_parts) >= 2:
        deno_ver = f"{dv_parts[0]}.{dv_parts[1]}"
    else:
        deno_ver = dv_parsed

    drifts = []
    for fname, content in docs.items():
        for m in DENO_DOC_RE.finditer(content):
            doc_ver = m.group("ver") or m.group("ver2")
            if doc_ver is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            doc_parts = doc_ver.split(".")
            if len(doc_parts) >= 2:
                doc_ver_norm = f"{doc_parts[0]}.{doc_parts[1]}"
            else:
                doc_ver_norm = doc_ver
            if doc_ver_norm != deno_ver:
                drifts.append({
                    "file": fname,
                    "doc_version": doc_ver,
                    "deno_json_version": deno_ver,
                    "pos": m.start(),
                })
                break
    return drifts
