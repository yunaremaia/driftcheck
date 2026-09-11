"""Mise.toml drift detection: mise.toml (rtx/asdf successor) vs README mentions."""
from __future__ import annotations
import re
from pathlib import Path

try:
    import tomllib  # Python 3.11+ stdlib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

# README mention patterns (shared with tool_versions detector)
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


def parse_mise_tools(text: str) -> dict[str, str]:
    """Parse ``mise.toml`` ``[tools]`` section into ``{tool: version}`` dict.

    Supports plain string specs (``node = "22"``) and dict specs
    (``python = {version = "3.12", virtualenv = ".venv"}``).
    """
    if tomllib is None:
        return {}
    try:
        data = tomllib.loads(text)
    except Exception:
        return {}

    tools_raw = data.get("tools", {})
    if not isinstance(tools_raw, dict):
        return {}

    result: dict[str, str] = {}
    for tool, spec in tools_raw.items():
        if isinstance(spec, str):
            result[tool] = spec
        elif isinstance(spec, dict) and "version" in spec:
            result[tool] = str(spec["version"])
    return result


def find_mise_drift(mise_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between ``mise.toml`` and README mentions.

    Returns list of ``{file, tool, doc_version, mise_version, pos}``.
    """
    if not mise_text.strip():
        return []

    tools = parse_mise_tools(mise_text)
    if not tools:
        return []

    drifts: list[dict] = []
    for fname, content in docs.items():
        for tool, version in tools.items():
            pat = TOOL_PATTERNS.get(tool)
            if not pat:
                continue
            for m in pat.finditer(content):
                doc_version = m.group(1)
                norm_doc = doc_version.lstrip("v")
                norm_tool = version.lstrip("v")
                doc_parts = norm_doc.split(".")
                tool_parts = norm_tool.split(".")
                if len(doc_parts) == 1:
                    doc_parts.append("0")
                if len(tool_parts) == 1:
                    tool_parts.append("0")
                if doc_parts[0] != tool_parts[0] or doc_parts[1] != tool_parts[1]:
                    drifts.append({
                        "file": fname,
                        "tool": tool,
                        "doc_version": doc_version,
                        "mise_version": version,
                        "pos": m.start(),
                    })
    return drifts
