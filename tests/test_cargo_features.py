"""Tests for Cargo.toml feature flag drift."""
from driftcheck.detectors.cargo_features import (
    find_cargo_feature_drift,
    parse_cargo_features,
)


CARGO = """
[package]
name = "demo"

[features]
default = ["serde"]
serde = ["dep:serde"]
async = ["tokio"]
"""


def test_parse_features():
    assert parse_cargo_features(CARGO) == {"default", "serde", "async"}


def test_advertised_unknown_feature():
    docs = {"README.md": 'Enable it with `features = ["serde", "missing"]`.\n'}
    drifts = find_cargo_feature_drift(CARGO, docs)
    assert any(d["feature"] == "missing" for d in drifts)


def test_defined_feature_missing_from_list():
    docs = {"README.md": 'features = ["serde"]\n'}
    drifts = find_cargo_feature_drift(CARGO, docs)
    assert any(d["feature"] == "async" for d in drifts)
    assert not any(d["feature"] == "default" for d in drifts)


def test_cli_flag_unknown_feature():
    docs = {"README.md": "cargo build --features ghost\n"}
    drifts = find_cargo_feature_drift(CARGO, docs)
    assert any(d["feature"] == "ghost" for d in drifts)


def test_no_docs_inventory_is_quiet():
    docs = {"README.md": "This crate is fast.\n"}
    assert find_cargo_feature_drift(CARGO, docs) == []


def test_quoted_feature_mention():
    docs = {"README.md": 'Turn on feature "async" and feature "nope".\n'}
    drifts = find_cargo_feature_drift(CARGO, docs)
    features = {d["feature"] for d in drifts}
    assert "nope" in features
    assert "async" not in features


def test_scan_repo_cargo_features(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "Cargo.toml").write_text("[features]\nserde = []\n", encoding="utf-8")
    (tmp_path / "README.md").write_text('features = ["missing"]\n', encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["feature"] == "missing" for item in result["cargo_feature_drifts"])
