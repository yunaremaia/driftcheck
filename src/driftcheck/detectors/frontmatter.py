"""Drift between YAML frontmatter in Markdown and toolchain version pins."""
from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|$)", re.S)
_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)*)")
_PKG_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.M)
_NODE_RE = re.compile(r'"node"\s*:\s*"([^"]+)"')
_PY_RE = re.compile(r'^requires-python\s*=\s*"([^"]+)"', re.M)
_GO_RE = re.compile(r"^\s*go\s+(\d+\.\d+(?:\.\d+)?)", re.M)
_RUST_TOOLCHAIN_RE = re.compile(r'channel\s*=\s*"(\d+(?:\.\d+){0,2})"')
_RUST_CARGO_RE = re.compile(r'rust-version\s*=\s*"(\d+(?:\.\d+){0,2})"')
_JSON_VERSION_RE = re.compile(r'"version"\s*:\s*"([^"]+)"')

_FIELD_SOURCES = {
    "rust_version": "Rust",
    "node_version": "Node.js",
    "python_version": "Python",
    "go_version": "Go",
}


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return scalar fields from a leading YAML frontmatter block."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for raw in match.group("body").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        value = value.strip().strip('"').strip("'")
        if value and not value.startswith("|") and not value.startswith(">"):
            fields[key.strip().lower()] = value
    return fields


def _major_minor(version: str) -> str:
    match = _VERSION_RE.search(version)
    if not match:
        return ""
    parts = match.group(1).split(".")
    return parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[1]}"


def _section_version(text: str, section: str) -> str | None:
    current = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            continue
        if current == section:
            match = _PKG_VERSION_RE.match(stripped)
            if match:
                return match.group(1)
    return None


def package_versions(cargo_text: str, pyproject_text: str, package_text: str) -> list[str]:
    """Collect literal package versions from Cargo, pyproject, and package.json."""
    found: list[str] = []
    for text, section in ((cargo_text, "package"), (pyproject_text, "project")):
        version = _section_version(text, section)
        if version:
            found.append(version)
    match = _JSON_VERSION_RE.search(package_text)
    if match:
        found.append(match.group(1))
    return found


def toolchain_versions(
    cargo_text: str,
    toolchain_text: str,
    package_text: str,
    pyproject_text: str,
    gomod_text: str,
    version_files: dict[str, str],
) -> dict[str, str]:
    """Return {frontmatter field: toolchain version} for fields we can check."""
    found: dict[str, str] = {}
    rust = _RUST_TOOLCHAIN_RE.search(toolchain_text) or _RUST_CARGO_RE.search(cargo_text)
    if rust:
        found["rust_version"] = rust.group(1)
    node = _NODE_RE.search(package_text)
    node_ver = node.group(1) if node else version_files.get(".node-version", "")
    if _major_minor(node_ver):
        found["node_version"] = node_ver.strip()
    py_match = _PY_RE.search(pyproject_text)
    py_ver = py_match.group(1) if py_match else version_files.get(".python-version", "")
    if _major_minor(py_ver):
        found["python_version"] = py_ver.strip()
    go_match = _GO_RE.search(gomod_text)
    if go_match:
        found["go_version"] = go_match.group(1)
    return found


def find_frontmatter_drift(
    docs: dict[str, str],
    cargo_text: str = "",
    toolchain_text: str = "",
    package_text: str = "",
    pyproject_text: str = "",
    gomod_text: str = "",
    version_files: dict[str, str] | None = None,
) -> list[dict]:
    """Flag frontmatter versions that disagree with the toolchain on major.minor."""
    versions = version_files or {}
    tools = toolchain_versions(
        cargo_text, toolchain_text, package_text, pyproject_text, gomod_text, versions,
    )
    packages = package_versions(cargo_text, pyproject_text, package_text)
    drifts: list[dict] = []
    for fname, content in docs.items():
        fields = parse_frontmatter(content)
        if not fields:
            continue
        doc_version = fields.get("version", "")
        doc_key = _major_minor(doc_version)
        if doc_key and packages and all(_major_minor(pkg) != doc_key for pkg in packages):
            expected = packages[0]
            drifts.append({
                "file": fname,
                "tool": "version",
                "doc_version": doc_version,
                "config_version": expected,
                "detail": f"frontmatter version {doc_version} in {fname} should be {expected}",
                "pos": 0,
            })
        for field, label in _FIELD_SOURCES.items():
            raw = fields.get(field, "")
            expected = tools.get(field, "")
            if not raw or not expected:
                continue
            if _major_minor(raw) == _major_minor(expected):
                continue
            drifts.append({
                "file": fname,
                "tool": label,
                "doc_version": raw,
                "config_version": expected,
                "detail": (
                    f"frontmatter {field} {raw} in {fname} should be {expected}"
                ),
                "pos": 0,
            })
    return drifts
