"""Integration tests for Node.js drift detection."""
from driftcheck.detectors.node import (
    parse_node_version_from_package,
    find_node_drift,
)


class TestParseNodeVersion:
    def test_simple(self):
        assert parse_node_version_from_package('{"engines": {"node": ">=18.0.0"}}') == "18"

    def test_caret(self):
        assert parse_node_version_from_package('{"engines": {"node": "^20.0.0"}}') == "20"

    def test_missing(self):
        assert parse_node_version_from_package('{"name": "test"}') is None

    def test_invalid_json(self):
        assert parse_node_version_from_package("not json") is None


class TestFindNodeDrift:
    def test_drift_detected(self):
        pkg = '{"engines": {"node": "20.0.0"}}'
        docs = {"README.md": "Requires Node.js 18"}
        drifts = find_node_drift(pkg, docs)
        assert len(drifts) >= 1
        assert drifts[0]["doc_version"] == "18"

    def test_no_drift(self):
        pkg = '{"engines": {"node": "20.0.0"}}'
        docs = {"README.md": "Requires Node.js 20"}
        drifts = find_node_drift(pkg, docs)
        assert drifts == []

    def test_no_node_in_docs(self):
        pkg = '{"engines": {"node": "20.0.0"}}'
        docs = {"README.md": "No node mention here"}
        drifts = find_node_drift(pkg, docs)
        assert drifts == []
