"""Bazel version drift detection."""

from __future__ import annotations

import re
from pathlib import Path

BAZEL_DEP_RE = re.compile(
    r"bazel_dep\s*\(.*?name\s*=\s*[\"'](?P<name>[^\"']+)[\"'].*?version\s*=\s*[\"'](?P<version>[^\"']+)[\"'].*?\)",
    re.DOTALL,
)
HTTP_ARCHIVE_RE = re.compile(
    r"http_archive\s*\(.*?name\s*=\s*[\"'](?P<name>[^\"']+)[\"'].*?urls?\s*=\s*\[(?P<urls>.*?)\].*?\)",
    re.DOTALL,
)
URL_VERSION_RE = re.compile(
    r"(?:/|[-_])v?(?P<version>\d+\.\d+(?:\.\d+)?)(?:[./_-]|$)", re.IGNORECASE
)


def _docs(root: Path) -> dict[str, str]:
    path = root / "README.md"
    return (
        {"README.md": path.read_text(encoding="utf-8", errors="replace")}
        if path.exists()
        else {}
    )


def _doc_version(content: str, name: str) -> tuple[str, int] | None:
    pattern = re.compile(
        rf"\b{re.escape(name)}\s*[:=@]?\s*v?(?P<version>\d+(?:\.\d+)+)", re.IGNORECASE
    )
    match = pattern.search(content)
    return (match.group("version"), match.start()) if match else None


def _add(
    drifts: list[dict], docs: dict[str, str], name: str, pinned: str, source: str
) -> None:
    for filename, content in docs.items():
        found = _doc_version(content, name)
        if found and found[0] != pinned:
            drifts.append(
                {
                    "file": filename,
                    "tool": name,
                    "doc_version": found[0],
                    "config_version": pinned,
                    "source": source,
                    "pos": found[1],
                }
            )


def find_bazel_drift(root: Path) -> list[dict]:
    """Detect Bazel and Bazel dependency pins that disagree with README mentions."""
    docs = _docs(root)
    drifts: list[dict] = []
    bazelversion = root / ".bazelversion"
    if bazelversion.exists():
        pinned = (
            bazelversion.read_text(encoding="utf-8", errors="replace")
            .strip()
            .splitlines()[0]
            .strip()
        )
        if pinned:
            _add(drifts, docs, "Bazel", pinned, ".bazelversion")
    module = root / "MODULE.bazel"
    if module.exists():
        for match in BAZEL_DEP_RE.finditer(
            module.read_text(encoding="utf-8", errors="replace")
        ):
            _add(
                drifts,
                docs,
                match.group("name"),
                match.group("version"),
                "MODULE.bazel",
            )
    workspace = root / "WORKSPACE.bazel"
    if workspace.exists():
        text = workspace.read_text(encoding="utf-8", errors="replace")
        for match in HTTP_ARCHIVE_RE.finditer(text):
            version = URL_VERSION_RE.search(match.group("urls"))
            if version:
                _add(
                    drifts,
                    docs,
                    match.group("name"),
                    version.group("version"),
                    "WORKSPACE.bazel",
                )
    return drifts
