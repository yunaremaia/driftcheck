"""Rust workspace member version drift detection.

Detects version drift between:
1. Root Cargo.toml [workspace.package] version vs member crate versions
2. Cross-crate version consensus (members vs majority)
3. Cargo.toml vs README badge/shield drift
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Regex patterns
WORKSPACE_PACKAGE_VER_RE = re.compile(
    r'\[workspace\.package\][^\[]*?version\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"',
    re.DOTALL,
)
WORKSPACE_MEMBERS_RE = re.compile(
    r"\[workspace\][^\[]*?members\s*=\s*\[(?P<members>[^\]]*)\]",
    re.DOTALL,
)
CRATE_VERSION_RE = re.compile(
    r'^version\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"',
    re.MULTILINE,
)
CRATES_IO_BADGE_RE = re.compile(
    r'https://img\.shields\.io/crates/v/(?P<crate>[^/\s"\']+)(?:/(?P<ver>[0-9]+(?:\.[0-9]+){0,2}))?',
)
CRATES_IO_SVG_RE = re.compile(
    r'https://crates\.io/crates/(?P<crate>[^/\s"\']+)/(?P<ver>[0-9]+(?:\.[0-9]+){0,2})',
)


def _parse_toml_simple(text: str) -> dict[str, Any]:
    """Minimal TOML parser for Cargo.toml workspace sections."""
    result: dict[str, Any] = {}
    m = WORKSPACE_PACKAGE_VER_RE.search(text)
    if m:
        result["workspace_version"] = m.group("ver")
    m = WORKSPACE_MEMBERS_RE.search(text)
    if m:
        members_str = m.group("members")
        members = [p.strip().strip('"').strip("'") for p in members_str.split(",")]
        result["members"] = [m for m in members if m]
    return result


def _expand_member_patterns(root: Path, members: list[str]) -> dict[str, str]:
    """Expand member patterns like 'crates/*' to actual Cargo.toml paths.

    Returns {relative_path: cargo_toml_text}.
    """
    result: dict[str, str] = {}
    for pattern in members:
        if "*" in pattern:
            prefix = pattern.rstrip("*").rstrip("/")
            prefix_path = root / prefix
            if prefix_path.is_dir():
                for cargo_path in prefix_path.glob("*/Cargo.toml"):
                    rel = str(cargo_path.relative_to(root))
                    result[rel] = cargo_path.read_text(encoding="utf-8")
        else:
            # Exact path
            direct = root / pattern
            if direct.is_file():
                result[pattern] = direct.read_text(encoding="utf-8")
            elif (direct / "Cargo.toml").is_file():
                rel = f"{pattern}/Cargo.toml"
                result[rel] = (direct / "Cargo.toml").read_text(encoding="utf-8")
    return result


def _extract_crate_versions(members: dict[str, str]) -> dict[str, str]:
    """Extract version from each member Cargo.toml."""
    versions: dict[str, str] = {}
    for path, text in members.items():
        m = CRATE_VERSION_RE.search(text)
        if m:
            versions[path] = m.group("ver")
    return versions


def _find_majority_version(versions: dict[str, str]) -> str | None:
    """Find the most common version."""
    if not versions:
        return None
    counts: dict[str, int] = {}
    for v in versions.values():
        counts[v] = counts.get(v, 0) + 1
    majority = max(counts, key=lambda k: counts[k])
    return majority if counts[majority] > 1 else None


def _read_text_safe(path: Path) -> str | None:
    """Read file text safely."""
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > 1_000_000:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def find_rust_workspace_drift(root: Path) -> list[dict]:
    """Detect version drift between workspace root, members, and READMEs.

    Args:
        root: repo root path.

    Returns:
        List of drift findings.
    """
    findings: list[dict] = []

    # 1. Read root Cargo.toml
    root_cargo = _read_text_safe(root / "Cargo.toml")
    if not root_cargo:
        return findings

    ws_info = _parse_toml_simple(root_cargo)
    ws_version = ws_info.get("workspace_version")
    members_patterns = ws_info.get("members", [])

    if not ws_version and not members_patterns:
        return findings

    # 2. Expand member patterns
    members = _expand_member_patterns(root, members_patterns)
    if not members:
        return findings

    # 3. Extract versions
    member_versions = _extract_crate_versions(members)

    # 4. Compare each member version vs workspace version
    if ws_version:
        for path, ver in member_versions.items():
            if ver != ws_version:
                findings.append(
                    {
                        "file": path,
                        "kind": "rust_workspace_member_drift",
                        "version": ver,
                        "expected_version": ws_version,
                        "detail": f"Member {path} has version {ver}, workspace requires {ws_version}",
                        "suggestion": f'Update version = "{ws_version}" in {path}',
                        "pos": 0,
                    }
                )

    # 5. Cross-crate consensus
    majority = _find_majority_version(member_versions)
    if majority and len(member_versions) > 2:
        for path, ver in member_versions.items():
            if ver != majority and not any(f["file"] == path for f in findings):
                findings.append(
                    {
                        "file": path,
                        "kind": "rust_workspace_cross_crate_drift",
                        "version": ver,
                        "expected_version": majority,
                        "detail": f"Member {path} has version {ver}, majority is {majority}",
                        "suggestion": f'Consider updating version = "{majority}" in {path}',
                        "pos": 0,
                    }
                )

    # 6. Cargo.toml vs README badge drift
    for readme_path in root.glob("**/README.md"):
        rel_readme = str(readme_path.relative_to(root))
        readme_text = _read_text_safe(readme_path)
        if not readme_text:
            continue

        for regex in [CRATES_IO_BADGE_RE, CRATES_IO_SVG_RE]:
            for m in regex.finditer(readme_text):
                crate_name = m.group("crate")
                badge_ver = m.group("ver")
                if not badge_ver:
                    continue

                for member_path, member_text in members.items():
                    name_match = re.search(
                        r'^name\s*=\s*"(?P<name>[^"]+)"', member_text, re.MULTILINE
                    )
                    if name_match and name_match.group("name") == crate_name:
                        ver_match = CRATE_VERSION_RE.search(member_text)
                        if ver_match and ver_match.group("ver") != badge_ver:
                            findings.append(
                                {
                                    "file": rel_readme,
                                    "kind": "rust_workspace_badge_drift",
                                    "version": badge_ver,
                                    "expected_version": ver_match.group("ver"),
                                    "detail": (
                                        f"README badge shows {crate_name} v{badge_ver}, "
                                        f"Cargo.toml has v{ver_match.group('ver')}"
                                    ),
                                    "suggestion": f"Update badge URL to v{ver_match.group('ver')}",
                                    "pos": m.start(),
                                }
                            )

    return findings
