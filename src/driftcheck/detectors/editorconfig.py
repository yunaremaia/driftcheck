"""EditorConfig drift detection: .editorconfig vs README/IDE settings.

Detects drift between .editorconfig settings and:
- README mentions of coding style
- VSCode settings.json
- Prettier/ESLint config
"""
from __future__ import annotations
import re

# Match indent/style mentions in README
INDENT_RE = re.compile(
    r'(?:indent|indentation|spacing)\s*(?:size\s*)?[:=]?\s*(?P<size>\d+)|(\d+)\s*(?:spaces?|chars?|[-]space)',
    re.I,
)
STYLE_RE = re.compile(
    r'(?:tabs?|spaces?)\s*(?:only|for\s+indent)',
    re.I,
)
LINE_ENDING_RE = re.compile(
    r'(?:line\s+ending|eol|end\s+of\s+line)\s*(?:is|[:=])\s*(?P<style>lf|crlf|cr)',
    re.I,
)
CHARSET_RE = re.compile(
    r'charset\s*[:=]\s*(?P<charset>utf-8|utf-16|latin1|iso-8859-1)',
    re.I,
)


def parse_editorconfig(text: str) -> dict[str, str]:
    """Parse .editorconfig into a flat dict of settings."""
    config = {}
    current_section = None
    
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            continue
        
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip().lower()
            value = value.strip()
            config[key] = value
    
    return config


def find_editorconfig_drift(
    editorconfig_content: str | None,
    docs: dict[str, str],
    vscode_content: str | None = None,
) -> list[dict]:
    """Detect drift between .editorconfig and README/IDE settings."""
    if not editorconfig_content:
        return []
    
    config = parse_editorconfig(editorconfig_content)
    if not config:
        return []
    
    drifts = []
    
    # Check indent settings
    indent_size = config.get("indent_size")
    indent_style = config.get("indent_style")
    
    for doc_fname, doc_content in docs.items():
        # Check indent size mentions
        if indent_size:
            for m in INDENT_RE.finditer(doc_content):
                doc_size = m.group("size") or m.group(2)
                if doc_size and doc_size != indent_size:
                    drifts.append({
                        "file": doc_fname,
                        "detail": f".editorconfig indent_size={indent_size} but README mentions {doc_size}",
                        "editorconfig_setting": f"indent_size={indent_size}",
                        "doc_mention": f"indent={doc_size}",
                    })
        
        # Check indent style (tabs vs spaces)
        if indent_style:
            for m in STYLE_RE.finditer(doc_content):
                doc_style = "space" if "space" in m.group(0).lower() else "tab"
                expected = "space" if indent_style == "space" else "tab"
                if doc_style != expected:
                    drifts.append({
                        "file": doc_fname,
                        "detail": f".editorconfig indent_style={indent_style} but README mentions {doc_style}s",
                        "editorconfig_setting": f"indent_style={indent_style}",
                        "doc_mention": f"{doc_style}s",
                    })
        
        # Check line ending
        end_of_line = config.get("end_of_line")
        if end_of_line:
            for m in LINE_ENDING_RE.finditer(doc_content):
                doc_eol = m.group("style").lower()
                if doc_eol != end_of_line.lower():
                    drifts.append({
                        "file": doc_fname,
                        "detail": f".editorconfig end_of_line={end_of_line} but README mentions {doc_eol}",
                        "editorconfig_setting": f"end_of_line={end_of_line}",
                        "doc_mention": doc_eol,
                    })
    
    # Check VSCode settings.json consistency
    if vscode_content:
        vscode_indent = _extract_vscode_indent(vscode_content)
        if vscode_indent and indent_size and vscode_indent != indent_size:
            drifts.append({
                "file": ".vscode/settings.json",
                "detail": f".editorconfig indent_size={indent_size} but VSCode tabSize={vscode_indent}",
                "editorconfig_setting": f"indent_size={indent_size}",
                "vscode_setting": f"tabSize={vscode_indent}",
            })
    
    return drifts


def _extract_vscode_indent(text: str) -> str | None:
    """Extract tabSize from VSCode settings.json."""
    m = re.search(r'"tabSize"\s*:\s*(\d+)', text)
    return m.group(1) if m else None
