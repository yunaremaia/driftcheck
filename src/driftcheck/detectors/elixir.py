"""Elixir drift detection: mix.exs elixir version vs README."""
from __future__ import annotations
import re

MIX_ELIXIR_RE = re.compile(r'elixir:\s*"~>\s*([\d.]+)"', re.I)
ELIXIR_DOC_RE = re.compile(
    r'(?:elixir|require[s]?\s+elixir)\s*v?(\d+\.\d+(?:\.\d+)?)',
    re.I,
)


def parse_mix_elixir_version(text: str) -> str | None:
    """Parse Elixir version from mix.exs.

    Expects: elixir: "~> 1.15"
    Returns: "1.15" (without the ~> operator)
    """
    m = MIX_ELIXIR_RE.search(text)
    return m.group(1) if m else None


def find_elixir_drift(mix_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Elixir version drift between mix.exs and README.

    Args:
        mix_text: content of mix.exs
        docs: {relative_path: content} of README/CONTRIBUTING files

    Returns list of {file, doc_version, mix_version, pos}.
    """
    mix_ver = parse_mix_elixir_version(mix_text)
    if not mix_ver:
        return []

    drifts = []
    for rel_path, text in docs.items():
        for m in ELIXIR_DOC_RE.finditer(text):
            doc_ver = m.group(1)
            # Major.minor comparison (ignore patch differences)
            doc_parts = doc_ver.split(".")
            mix_parts = mix_ver.split(".")
            if doc_parts[:2] != mix_parts[:2]:
                drifts.append({
                    "file": rel_path,
                    "doc_version": doc_ver,
                    "mix_version": mix_ver,
                    "pos": m.start(),
                })
                break  # one drift per file
    return drifts
