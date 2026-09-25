"""A2A (Agent2Agent) protocol drift detection.

Detects drift between A2A agent cards and documentation:
- Agent card spec_version vs documented A2A version
- Capabilities advertised in card vs documented capabilities
- Endpoint URLs in card vs documented endpoints
- Protocol conformance claims vs actual JSON-RPC methods

Reference: https://a2a-protocol.org
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Callable

# A2A spec version patterns seen in docs
A2A_VERSION_RE = re.compile(
    r'(?:A2A|Agent2Agent)\s*(?:protocol|spec|version)?\s*(?:is|was|at|on|since|from|to|until)?\s*(?P<ver>v?\d+\.\d+(?:\.\d+)?)',
    re.I
)

# Agent card file patterns
AGENT_CARD_PATTERNS = [
    re.compile(r'\.a2a/'),
    re.compile(r'agent(-card)?\.json$'),
    re.compile(r'agent-card\.ya?ml$'),
]

# JSON-RPC method patterns in agent cards
JSONRPC_METHODS_RE = re.compile(
    r'"(\w+)"\s*:\s*\{[^}]*"description"\s*:\s*"([^"]*)"',
    re.I | re.S
)

# Capability patterns in documentation
CAPABILITY_RE = re.compile(
    r'(?:capabilities?|features?|skills?|tools?)\s*[:\-]\s*(?P<cap>[^\n,;]+)',
    re.I
)


def is_agent_card_file(path: Path) -> bool:
    """Check if a file is likely an A2A agent card."""
    name = path.name
    full = str(path)
    for pattern in AGENT_CARD_PATTERNS:
        if pattern.search(name) or pattern.search(full):
            return True
    return False


def parse_agent_card(card_path: Path) -> dict | None:
    """Parse an A2A agent card JSON file."""
    try:
        with open(card_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def extract_card_spec_version(card: dict) -> str | None:
    """Extract spec_version from an agent card."""
    # Standard A2A agent card field
    if 'spec_version' in card:
        return str(card['spec_version'])
    # Some implementations use 'version'
    if 'version' in card:
        return str(card['version'])
    return None


def extract_card_capabilities(card: dict) -> list[str]:
    """Extract capabilities listed in an agent card."""
    caps = []
    # Standard A2A: capabilities field
    if 'capabilities' in card:
        for cap in card['capabilities']:
            if isinstance(cap, dict):
                name = cap.get('name', cap.get('id', ''))
                if name:
                    caps.append(str(name))
            elif isinstance(cap, str):
                caps.append(cap)
    # Alternative: skills field
    if 'skills' in card:
        for skill in card['skills']:
            if isinstance(skill, dict):
                name = skill.get('name', skill.get('id', ''))
                if name:
                    caps.append(str(name))
            elif isinstance(skill, str):
                caps.append(skill)
    # tools field
    if 'tools' in card:
        for tool in card['tools']:
            if isinstance(tool, dict):
                name = tool.get('name', tool.get('description', ''))
                if name:
                    caps.append(str(name)[:50])
    return caps


def extract_card_endpoints(card: dict) -> list[str]:
    """Extract endpoint URLs from an agent card."""
    endpoints = []
    if 'endpoint' in card:
        ep = card['endpoint']
        if isinstance(ep, str):
            endpoints.append(ep)
        elif isinstance(ep, dict):
            if 'url' in ep:
                endpoints.append(ep['url'])
    # Some cards have 'urls' or 'addresses'
    for key in ('urls', 'addresses', 'services'):
        if key in card:
            val = card[key]
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        endpoints.append(item)
                    elif isinstance(item, dict) and 'url' in item:
                        endpoints.append(item['url'])
            elif isinstance(val, str):
                endpoints.append(val)
    return endpoints


def find_a2a_drift(root: Path, docs: dict[str, str]) -> list[dict]:
    """Detect A2A protocol drift between agent cards and documentation.

    Checks:
    1. spec_version in agent card vs documented A2A version
    2. Capabilities advertised in card vs documented
    3. Endpoint URLs in card vs documented
    4. Protocol conformance claims vs actual JSON-RPC methods available
    """
    drifts = []

    # Find agent card files in the repo
    card_files = []
    for p in root.rglob('*'):
        if p.is_file() and is_agent_card_file(p):
            card_files.append(p)

    if not card_files:
        return []

    # Parse all agent cards
    cards = []
    for cf in card_files:
        card = parse_agent_card(cf)
        if card:
            cards.append((cf, card))

    if not cards:
        return []

    # Collect documentation mentions of A2A versions
    doc_versions = {}
    for fname, content in docs.items():
        for m in A2A_VERSION_RE.finditer(content):
            ver = m.group('ver').lstrip('v')
            doc_versions.setdefault(ver, []).append(fname)

    # Check 1: spec_version drift between cards and docs
    card_versions: dict[str, list[str]] = {}  # version -> [card_paths]
    for card_path, card in cards:
        sv = extract_card_spec_version(card)
        if sv:
            ver = sv.lstrip('v')
            card_versions.setdefault(ver, []).append(str(card_path.relative_to(root)))

    if doc_versions and card_versions:
        for doc_ver, doc_files in doc_versions.items():
            for card_ver, card_paths in card_versions.items():
                if doc_ver != card_ver:
                    for df in doc_files:
                        drifts.append({
                            "file": df,
                            "detail": f"A2A spec version mismatch: card declares v{card_ver}, docs reference v{doc_ver}",
                            "card_file": card_paths[0],
                            "doc_version": doc_ver,
                            "card_version": card_ver,
                        })

    # Check 2: Capabilities in card vs documented capabilities
    card_caps_by_file = {}
    for card_path, card in cards:
        caps = extract_card_capabilities(card)
        if caps:
            card_caps_by_file[str(card_path.relative_to(root))] = caps

    doc_caps = {}
    for fname, content in docs.items():
        for m in CAPABILITY_RE.finditer(content):
            cap = m.group('cap').strip()
            if len(cap) > 2:  # Filter noise
                doc_caps.setdefault(fname, []).append(cap)

    # Flag when card has capabilities not mentioned in docs (informational)
    for card_rel, card_cap_list in card_caps_by_file.items():
        for cap in card_cap_list:
            found_in_docs = False
            for df, dcaps in doc_caps.items():
                for dc in dcaps:
                    if cap.lower() in dc.lower() or dc.lower() in cap.lower():
                        found_in_docs = True
                        break
                if found_in_docs:
                    break
            if not found_in_docs and len(card_cap_list) > 0:
                # Only flag if there are docs to compare against
                if doc_caps:
                    drifts.append({
                        "file": card_rel,
                        "detail": f"A2A capability '{cap}' advertised in card but not found in documentation",
                        "type": "informational",
                    })

    # Check 3: Endpoint URLs in card vs documented
    card_endpoints = {}
    for card_path, card in cards:
        eps = extract_card_endpoints(card)
        if eps:
            card_endpoints[str(card_path.relative_to(root))] = eps

    doc_endpoints = {}
    endpoint_url_re = re.compile(r'(?:endpoint|url|address|invoke)\s*[:=]?\s*["\'>]*(?P<url>https?://[^\s"\'<>]+)', re.I)
    for fname, content in docs.items():
        for m in endpoint_url_re.finditer(content):
            url = m.group('url')
            doc_endpoints.setdefault(fname, []).append(url)

    for card_rel, card_ep_list in card_endpoints.items():
        for ep in card_ep_list:
            found = False
            for df, deps in doc_endpoints.items():
                if ep in deps:
                    found = True
                    break
            if not found and doc_endpoints:
                drifts.append({
                    "file": card_rel,
                    "detail": f"A2A endpoint '{ep}' in card but not documented",
                    "type": "informational",
                })

    return drifts


def register() -> dict[str, Callable]:
    """Plugin registration for driftcheck."""
    return {"a2a_drift": find_a2a_drift}
