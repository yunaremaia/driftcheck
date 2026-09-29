"""Julia drift: Project.toml [compat] and Manifest.toml vs README package versions."""
from __future__ import annotations

import re

_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)*)")
_MANIFEST_HEADER_RE = re.compile(r"^\[\[(?:deps\.)?([A-Za-z][A-Za-z0-9_]*)\]\]\s*$")
_MANIFEST_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"')
_DOC_RE = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9_]*)(?:\.jl)?\s+v?(?P<ver>\d+\.\d+(?:\.\d+)?)\b"
)


def _first_version(spec: str) -> str | None:
    match = _VERSION_RE.search(spec)
    return match.group(1) if match else None


def _major_minor(version: str) -> str:
    parts = version.split(".")
    return parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[1]}"


def parse_project_compat(text: str) -> dict[str, str]:
    """Return {package: version} from Project.toml [compat], skipping julia itself."""
    found: dict[str, str] = {}
    in_compat = False
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_compat = stripped == "[compat]"
            continue
        if not in_compat or "=" not in stripped:
            continue
        name, _, spec = stripped.partition("=")
        name = name.strip().strip('"').strip("'")
        if not name or name.lower() == "julia":
            continue
        version = _first_version(spec.strip().strip('"').strip("'"))
        if version:
            found[name] = version
    return found


def parse_manifest_versions(text: str) -> dict[str, str]:
    """Return {package: resolved version} from Manifest.toml."""
    found: dict[str, str] = {}
    current = ""
    for raw in text.splitlines():
        header = _MANIFEST_HEADER_RE.match(raw.strip())
        if header:
            current = header.group(1)
            continue
        if not current:
            continue
        match = _MANIFEST_VERSION_RE.match(raw.strip())
        if match and current.lower() != "julia":
            found.setdefault(current, match.group(1))
    return found


def find_julia_drift(
    project_text: str,
    manifest_text: str,
    docs: dict[str, str],
) -> list[dict]:
    """Flag README package versions whose major.minor differs from the Julia manifest.

    Resolved Manifest.toml versions win over [compat] bounds when both exist.
    """
    pins = parse_project_compat(project_text)
    pins.update(parse_manifest_versions(manifest_text))
    if not pins:
        return []

    drifts: list[dict] = []
    for fname, content in docs.items():
        seen: set[str] = set()
        for match in _DOC_RE.finditer(content):
            name = match.group("name")
            if name not in pins or name in seen:
                continue
            doc_ver = match.group("ver")
            pin = pins[name]
            if _major_minor(doc_ver) == _major_minor(pin):
                continue
            seen.add(name)
            drifts.append({
                "file": fname,
                "package": name,
                "doc_version": doc_ver,
                "manifest_version": pin,
                "detail": f"{name}.jl {doc_ver} in {fname} should be {pin} (Project.toml/Manifest.toml)",
                "pos": match.start(),
            })
    return drifts
