"""Dockerfile instruction drift detection: EXPOSE, HEALTHCHECK, WORKDIR, ENTRYPOINT, USER vs README mentions."""
from __future__ import annotations
import re

# Dockerfile instruction patterns
DOCKERFILE_INSTRUCTIONS = {
    "EXPOSE": re.compile(r'^EXPOSE\s+(?P<value>[\d\s,/]+)', re.MULTILINE | re.I),
    "HEALTHCHECK": re.compile(r'^HEALTHCHECK\s+(?P<value>.+)$', re.MULTILINE | re.I),
    "WORKDIR": re.compile(r'^WORKDIR\s+(?P<value>[\w./\-]+)', re.MULTILINE | re.I),
    "ENTRYPOINT": re.compile(r'^ENTRYPOINT\s+(?P<value>.+)$', re.MULTILINE | re.I),
    "USER": re.compile(r'^USER\s+(?P<value>[\w.\-]+)', re.MULTILINE | re.I),
}

# Doc mention patterns (README, etc.)
DOC_PATTERNS = {
    "EXPOSE": re.compile(r'(?:EXPOSE|exposes?|port[s]?)\s+(?P<value>[\d\s,/]+)', re.I),
    "HEALTHCHECK": re.compile(r'(?:HEALTHCHECK|health\s*check)\s*(?P<value>[\w\s./\-]+)?', re.I),
    "WORKDIR": re.compile(r'(?:WORKDIR|working\s*directory)(?:\s+is)?\s+(?P<value>/[\w./\-]+)', re.I),
    "ENTRYPOINT": re.compile(r'(?:ENTRYPOINT|entry\s*point)\s+(?P<value>[\w./\-]+)', re.I),
    "USER": re.compile(r'(?:USER|run\s*as)\s+(?P<value>[\w.\-]+)', re.I),
}


def parse_dockerfile_instructions(text: str) -> dict[str, str]:
    """Return {instruction: value} map of Dockerfile instructions."""
    result = {}
    for instr, pattern in DOCKERFILE_INSTRUCTIONS.items():
        m = pattern.search(text)
        if m:
            result[instr] = m.group("value").strip()
    return result


def find_dockerfile_instruction_drift(dockerfiles: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Dockerfile instructions and README mentions.

    Scans docs for patterns like 'EXPOSE 8080' or 'WORKDIR /app' and compares
    to the actual instruction in the Dockerfile. Returns drifts where the doc
    mentions a different value than what the Dockerfile sets.
    """
    # Collect all instructions across dockerfiles
    all_instructions: dict[str, str] = {}
    for fname, content in dockerfiles.items():
        for instr, value in parse_dockerfile_instructions(content).items():
            all_instructions[instr] = value

    if not all_instructions:
        return []

    drifts = []
    for fname, content in docs.items():
        for instr, pattern in DOC_PATTERNS.items():
            if instr not in all_instructions:
                continue
            m = pattern.search(content)
            if not m:
                continue
            doc_value = (m.group("value") or "").strip()
            dockerfile_value = all_instructions[instr]
            if doc_value and doc_value != dockerfile_value:
                drifts.append({
                    "file": fname,
                    "instruction": instr,
                    "doc_value": doc_value,
                    "dockerfile_value": dockerfile_value,
                    "pos": m.start(),
                })
    return drifts
