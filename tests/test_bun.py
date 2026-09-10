"""Integration tests for Bun drift detection."""
from driftcheck.detectors.bun import (
    parse_bun_version_from_package,
    find_bun_drift,
)


class TestParseBunVersion:
    def test_simple(self):
        # Returns major.minor
        assert parse_bun_version_from_package('{"engines": {"bun": "1.2.3"}}') == "1.2"

    def test_caret(self):
        assert parse_bun_version_from_package('{"engines": {"bun": "^1.2.0"}}') == "1.2"

    def test_missing(self):
        assert parse_bun_version_from_package('{"name": "test"}') is None

    def test_invalid_json(self):
        assert parse_bun_version_from_package("not json") is None


class TestFindBunDrift:
    def test_drift_detected(self):
        pkg = '{"engines": {"bun": "1.2.0"}}'
        docs = {"README.md": "Built with Bun 1.1"}
        drifts = find_bun_drift(pkg, docs)
        assert len(drifts) >= 1
        assert drifts[0]["doc_version"] == "1.1"

    def test_no_drift(self):
        pkg = '{"engines": {"bun": "1.2.0"}}'
        docs = {"README.md": "Built with Bun 1.2"}
        drifts = find_bun_drift(pkg, docs)
        assert drifts == []

    def test_empty_engines(self):
        pkg = '{"engines": {}}'
        docs = {"README.md": "Built with Bun 1.2"}
        drifts = find_bun_drift(pkg, docs)
        assert drifts == []

    def test_no_bun_in_docs(self):
        pkg = '{"engines": {"bun": "1.2.0"}}'
        docs = {"README.md": "No bun mention here"}
        drifts = find_bun_drift(pkg, docs)
        assert drifts == []
