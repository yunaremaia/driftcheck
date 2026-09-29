"""R drift: DESCRIPTION constraints and renv.lock pins vs README mentions."""
from __future__ import annotations

import json
import re

_FIELDS = ("Imports", "Depends", "Suggests")
_DEP_RE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9.]*)\s*(?:\(\s*[^0-9]*\s*(?P<ver>\d+\.\d+(?:\.\d+)*)\s*[^)]*\))?"
)
_DOC_RE = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9.]*)\s+v?(?P<ver>\d+\.\d+(?:\.\d+)?)\b"
)


def _major_minor(version: str) -> str:
    parts = version.split(".")
    return parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[1]}"


def parse_description_deps(text: str) -> dict[str, str]:
    """Return {package: lower-bound version} from Imports, Depends, and Suggests."""
    chunks: dict[str, list[str]] = {}
    current = ""
    for raw in text.splitlines():
        if raw and not raw[0].isspace() and ":" in raw:
            key, _, rest = raw.partition(":")
            current = key.strip() if key.strip() in _FIELDS else ""
            if current:
                chunks.setdefault(current, []).append(rest)
            continue
        if current and (raw.startswith(" ") or raw.startswith("\t")):
            chunks[current].append(raw)
    found: dict[str, str] = {}
    for blob in chunks.values():
        for match in _DEP_RE.finditer(" ".join(blob)):
            name = match.group("name")
            version = match.group("ver")
            if not version or name == "R":
                continue
            found.setdefault(name, version)
    return found


def parse_renv_lock(text: str) -> dict[str, str]:
    """Return {package: version} from an renv.lock JSON document."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    packages = data.get("Packages")
    if not isinstance(packages, dict):
        return {}
    found: dict[str, str] = {}
    for key, entry in packages.items():
        if not isinstance(entry, dict):
            continue
        version = entry.get("Version") or entry.get("version")
        name = entry.get("Package") or key
        if isinstance(name, str) and isinstance(version, str) and name != "R":
            found[name] = version
    return found


def find_r_drift(
    description_text: str,
    renv_text: str,
    docs: dict[str, str],
) -> list[dict]:
    """Flag README package versions that disagree with DESCRIPTION or renv.lock.

    A locked renv version overrides the DESCRIPTION bound for the same package.
    """
    pins = parse_description_deps(description_text)
    pins.update(parse_renv_lock(renv_text))
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
                "detail": f"{name} {doc_ver} in {fname} should be {pin} (DESCRIPTION/renv.lock)",
                "pos": match.start(),
            })
    return drifts
