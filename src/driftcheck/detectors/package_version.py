"""package.json version drift detection for documentation references."""
from __future__ import annotations

import json
import re


def parse_package_identity(package_text: str) -> tuple[str | None, str | None]:
    """Return (name, version) from package.json, or (None, None) when invalid."""
    if not package_text.strip():
        return None, None
    try:
        data = json.loads(package_text)
    except (json.JSONDecodeError, TypeError):
        return None, None
    name = data.get("name")
    version = data.get("version")
    return (
        name if isinstance(name, str) and name else None,
        version if isinstance(version, str) and version else None,
    )


def _doc_patterns(package: str) -> list[tuple[str, re.Pattern[str]]]:
    escaped = re.escape(package)
    return [
        (
            "badge",
            re.compile(
                rf"https://img\.shields\.io/npm/v/{escaped}/(?P<ver>\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)",
                re.I,
            ),
        ),
        (
            "install",
            re.compile(
                rf"\bnpm\s+(?:install|i|add)\s+{escaped}@(?P<ver>\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)",
                re.I,
            ),
        ),
        (
            "changelog",
            re.compile(
                r"(?m)^#{2,3}\s*\[(?P<ver>\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)\]"
            ),
        ),
    ]


def find_package_version_drift(
    package_text: str,
    docs: dict[str, str],
) -> list[dict]:
    """Compare package.json version against explicit version references in docs."""
    package, version = parse_package_identity(package_text)
    if not package or not version:
        return []

    drifts: list[dict] = []
    for filename, content in docs.items():
        for kind, pattern in _doc_patterns(package):
            for match in pattern.finditer(content):
                doc_version = match.group("ver")
                if doc_version == version:
                    continue
                drifts.append(
                    {
                        "file": filename,
                        "kind": kind,
                        "package": package,
                        "doc_version": doc_version,
                        "package_version": version,
                        "pos": match.start("ver"),
                    }
                )
    return drifts


def fix_package_version_reference(content: str, drift: dict) -> str:
    """Replace the version for one known package-version drift."""
    old = drift["doc_version"]
    new = drift["package_version"]
    package = drift["package"]
    kind = drift["kind"]

    for pattern_kind, pattern in _doc_patterns(package):
        if pattern_kind != kind:
            continue

        def replace(match: re.Match[str]) -> str:
            if match.group("ver") != old:
                return match.group(0)
            start, end = match.span("ver")
            whole = match.group(0)
            rel_start = start - match.start()
            rel_end = end - match.start()
            return whole[:rel_start] + new + whole[rel_end:]

        return pattern.sub(replace, content)
    return content
