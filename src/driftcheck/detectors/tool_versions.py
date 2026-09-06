"""Tool-versions drift detection: .tool-versions (asdf/mise) vs README."""
from __future__ import annotations
import re
from pathlib import Path

# Map of tool name in .tool-versions to common README mention patterns
TOOL_PATTERNS = {
    "node": re.compile(r'(?:node\.?js|node)\s*v?(\d+(?:\.\d+)*)', re.I),
    "python": re.compile(r'python\s*v?(\d+(?:\.\d+)*)', re.I),
    "go": re.compile(r'(?:golang|go)\s*v?(\d+(?:\.\d+)*)', re.I),
    "rust": re.compile(r'rust\s*v?(\d+(?:\.\d+)*)', re.I),
    "ruby": re.compile(r'ruby\s*v?(\d+(?:\.\d+)*)', re.I),
    "java": re.compile(r'java\s*v?(\d+(?:\.\d+)*)', re.I),
    "php": re.compile(r'php\s*v?(\d+(?:\.\d+)*)', re.I),
    "dotnet": re.compile(r'(?:dotnet|\.net)\s*v?(\d+(?:\.\d+)*)', re.I),
}

TOOL_VERSION_RE = re.compile(r'^(?P<tool>\S+)\s+(?P<version>\S+)', re.MULTILINE)


def parse_tool_versions(text: str) -> dict[str, str]:
    """Parse .tool-versions file content into {tool: version} dict."""
    result = {}
    for m in TOOL_VERSION_RE.finditer(text):
        tool = m.group("tool").lower()
        version = m.group("version")
        result[tool] = version
    return result


def find_tool_versions_drift(tool_versions_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between .tool-versions (asdf/mise) and README mentions.

    Returns list of {file, tool, doc_version, tool_versions_version, pos}.
    """
    if not tool_versions_text.strip():
        return []

    tools = parse_tool_versions(tool_versions_text)
    if not tools:
        return []

    drifts = []
    for fname, content in docs.items():
        for tool, version in tools.items():
            pat = TOOL_PATTERNS.get(tool)
            if not pat:
                continue
            for m in pat.finditer(content):
                doc_version = m.group(1)
                # Normalize versions for comparison (strip leading 'v')
                norm_doc = doc_version.lstrip("v")
                norm_tool = version.lstrip("v")
                # Compare major.minor (ignore patch differences)
                doc_parts = norm_doc.split(".")
                tool_parts = norm_tool.split(".")
                # Pad single-number versions (e.g., "18" -> ["18", "0"])
                if len(doc_parts) == 1:
                    doc_parts.append("0")
                if len(tool_parts) == 1:
                    tool_parts.append("0")
                if doc_parts[0] != tool_parts[0] or doc_parts[1] != tool_parts[1]:
                        drifts.append({
                            "file": fname,
                            "tool": tool,
                            "doc_version": doc_version,
                            "tool_versions_version": version,
                            "pos": m.start(),
                        })
    return drifts
