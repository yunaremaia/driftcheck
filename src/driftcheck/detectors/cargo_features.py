"""Drift between Cargo.toml [features] and feature lists in documentation."""
from __future__ import annotations

import re

_FEATURES_LIST_RE = re.compile(
    r"features\s*=\s*\[(?P<body>[^\]]*)\]",
    re.I,
)
_FEATURE_FLAG_RE = re.compile(
    r"--features?\s+(?P<body>[A-Za-z0-9_-]+(?:\s*,\s*[A-Za-z0-9_-]+)*)"
)
_FEATURE_QUOTED_RE = re.compile(
    r"""feature\s+[`"'](?P<name>[A-Za-z0-9_-]+)[`"']""",
    re.I,
)


def parse_cargo_features(text: str) -> set[str]:
    """Return feature names declared in the ``[features]`` table."""
    features: set[str] = set()
    in_features = False
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_features = stripped == "[features]"
            continue
        if not in_features or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip().strip('"').strip("'")
        if key and re.fullmatch(r"[A-Za-z0-9_-]+", key):
            features.add(key)
    return features


def _names_from_list(body: str) -> set[str]:
    names: set[str] = set()
    for part in body.split(","):
        name = part.strip().strip('"').strip("'").strip("`")
        if name and re.fullmatch(r"[A-Za-z0-9_-]+", name):
            names.add(name)
    return names


def advertised_features(docs: dict[str, str]) -> dict[str, set[str]]:
    """Return {doc file: advertised feature names}."""
    found: dict[str, set[str]] = {}
    for fname, content in docs.items():
        names: set[str] = set()
        for match in _FEATURES_LIST_RE.finditer(content):
            names |= _names_from_list(match.group("body"))
        for match in _FEATURE_FLAG_RE.finditer(content):
            names |= _names_from_list(match.group("body"))
        for match in _FEATURE_QUOTED_RE.finditer(content):
            names.add(match.group("name"))
        if names:
            found[fname] = names
    return found


def find_cargo_feature_drift(cargo_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect Cargo features advertised in docs but not defined, and the reverse.

    Undefined-in-docs findings are emitted only when a doc file contains an
    explicit ``features = [...]`` list, so prose that never inventories
    features is left alone.
    """
    defined = parse_cargo_features(cargo_text)
    advertised = advertised_features(docs)
    if not defined and not advertised:
        return []

    comparable = defined - {"default"}
    drifts: list[dict] = []
    explicit_lists: dict[str, set[str]] = {}
    for fname, content in docs.items():
        listed: set[str] = set()
        for match in _FEATURES_LIST_RE.finditer(content):
            listed |= _names_from_list(match.group("body"))
        if listed:
            explicit_lists[fname] = listed

    for fname, names in advertised.items():
        for name in sorted(names - defined):
            drifts.append({
                "file": fname,
                "feature": name,
                "detail": f"feature `{name}` is advertised in {fname} but not defined in Cargo.toml",
                "pos": 0,
            })

    if comparable and explicit_lists:
        documented = set().union(*explicit_lists.values())
        for name in sorted(comparable - documented):
            fname = next(iter(explicit_lists))
            drifts.append({
                "file": fname,
                "feature": name,
                "detail": (
                    f"feature `{name}` is defined in Cargo.toml but missing "
                    f"from the features list in {fname}"
                ),
                "pos": 0,
            })
    return drifts
