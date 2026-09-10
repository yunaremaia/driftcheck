"""Integration tests for Rust toolchain drift detection."""
from driftcheck.detectors.rust import (
    parse_toolchain_version,
    parse_cargo_rust_version,
    find_rust_drift,
    find_rust_drift_multi,
)


class TestParseToolchain:
    def test_simple(self):
        assert parse_toolchain_version('[toolchain]\nchannel = "1.96.1"') == "1.96.1"

    def test_no_channel(self):
        assert parse_toolchain_version('[toolchain]\nedition = "2024"') is None


class TestParseCargoRustVersion:
    def test_simple(self):
        assert parse_cargo_rust_version('[package]\nrust-version = "1.96.1"') == "1.96.1"

    def test_missing(self):
        assert parse_cargo_rust_version('[package]\nname = "test"') is None


class TestFindRustDrift:
    def test_drift_detected(self):
        tc = '[toolchain]\nchannel = "1.96.1"'
        docs = {"README.md": "Built with Rust 1.95.0"}
        drifts = find_rust_drift(tc, docs)
        assert len(drifts) >= 1
        assert drifts[0]["doc_version"] == "1.95.0"

    def test_no_drift(self):
        tc = '[toolchain]\nchannel = "1.96.1"'
        docs = {"README.md": "Built with Rust 1.96.1"}
        drifts = find_rust_drift(tc, docs)
        assert drifts == []

    def test_major_minor_match(self):
        tc = '[toolchain]\nchannel = "1.96"'
        docs = {"README.md": "Built with Rust 1.96.5"}
        drifts = find_rust_drift(tc, docs)
        assert drifts == []

    def test_multi_source(self):
        tc = '[toolchain]\nchannel = "1.96.1"'
        cargo = '[package]\nrust-version = "1.96.1"'
        docs = {"README.md": "Built with Rust 1.95.0"}
        drifts = find_rust_drift_multi(tc, cargo, docs)
        assert len(drifts) >= 1
