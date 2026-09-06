"""Rust toolchain drift detection: rust-toolchain.toml and Cargo.toml rust-version."""
from __future__ import annotations
import re

TOOLCHAIN_RE = re.compile(r'channel\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"')
DOC_RE = re.compile(r'Rust\s+(?P<ver>[0-9]+\.[0-9]+\.[0-9]+)')

CARGO_RE = re.compile(r'rust-version\s*=\s*"(?P<ver>[0-9]+(?:\.[0-9]+){0,2})"')

# Looser doc regex for multi-source: accepts major.minor (e.g. "Rust 1.96") too.
DOC_RE_LOOSE = re.compile(r'Rust\s+(?P<ver>[0-9]+(?:\.[0-9]+){1,2})')


def parse_toolchain_version(text: str) -> str | None:
    m = TOOLCHAIN_RE.search(text)
    return m.group("ver") if m else None


def find_rust_drift(toolchain_text: str, docs: dict[str, str]) -> list[dict]:
    """Return list of drifts vs a rust-toolchain.toml source.

    Delegates to find_rust_drift_multi for consistent minor-aware comparison.
    """
    return find_rust_drift_multi(toolchain_text=toolchain_text, cargo_text="", docs=docs)


def parse_cargo_rust_version(text: str) -> str | None:
    """Parse `rust-version = "1.96.1"` from Cargo.toml."""
    m = CARGO_RE.search(text)
    return m.group("ver") if m else None


def _minor(v: str) -> str:
    """Best-effort major.minor of a semver-ish string (handles '1.96' and '1.96.1')."""
    parts = v.split(".")
    return ".".join(parts[:2])


def find_rust_drift_multi(toolchain_text: str, cargo_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Rust doc drift using rust-toolchain.toml and/or Cargo.toml rust-version.

    A doc version drifts when it does not match the toolchain on the shared
    precision (full version if both have a patch, major.minor otherwise).
    Returns list of {file, doc_version, toolchain_version?, cargo_version?}.
    """
    tv = parse_toolchain_version(toolchain_text)
    cv = parse_cargo_rust_version(cargo_text)
    # resolve authoritative version: prefer toolchain, fall back to cargo
    if tv and cv:
        authoritative = tv if _minor(tv) == _minor(cv) or tv == cv else (tv if len(tv) >= len(cv) else cv)
    else:
        authoritative = tv or cv
    if not authoritative:
        return []
    # build comparison key: full if patch present, else major.minor
    auth_has_patch = authoritative.count(".") == 2
    auth_key = authoritative if auth_has_patch else _minor(authoritative)

    drifts = []
    for fname, content in docs.items():
        for m in DOC_RE_LOOSE.finditer(content):
            dv = m.group("ver")
            # When the authoritative version lacks a patch, compare on major.minor
            # only (so "1.96" and "1.96.1" are treated as matching).
            if not auth_has_patch:
                doc_key = _minor(dv)
            else:
                doc_key = dv if dv.count(".") == 2 else _minor(dv)
            if doc_key != auth_key:
                entry = {"file": fname, "doc_version": dv, "pos": m.start()}
                if tv:
                    entry["toolchain_version"] = tv
                if cv:
                    entry["cargo_version"] = cv
                drifts.append(entry)
                break  # one per file
    return drifts
