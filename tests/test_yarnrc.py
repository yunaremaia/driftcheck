"""Tests for yarnrc drift detection."""
import pytest
from driftcheck.detectors.yarnrc import (
    parse_yarnrc_version,
    find_yarnrc_drift,
    _versions_match,
)


def test_parse_yarnrc_version_from_path():
    text = "yarnPath: .yarn/releases/yarn-3.6.1.cjs\n"
    assert parse_yarnrc_version(text) == "3.6.1"


def test_parse_yarnrc_version_from_field():
    text = "yarnVersion: 4.0.0\n"
    assert parse_yarnrc_version(text) == "4.0.0"


def test_parse_yarnrc_version_with_comments():
    text = "# Yarn config\nyarnPath: .yarn/releases/yarn-3.6.1.cjs\n"
    assert parse_yarnrc_version(text) == "3.6.1"


def test_parse_yarnrc_version_empty():
    assert parse_yarnrc_version("") is None


def test_parse_yarnrc_version_no_version():
    text = "nodeLinker: node-modules\n"
    assert parse_yarnrc_version(text) is None


def test_versions_match_exact():
    assert _versions_match("3.6.1", "3.6.1")


def test_versions_match_major_minor():
    assert _versions_match("3.6", "3.6.1")


def test_versions_match_major_only():
    assert _versions_match("3", "3.6.1")


def test_versions_match_mismatch():
    assert not _versions_match("3.5", "3.6.1")


def test_find_yarnrc_drift_no_drift():
    yarnrc = "yarnPath: .yarn/releases/yarn-3.6.1.cjs\n"
    docs = {"README.md": "This project uses yarn 3.6.1"}
    assert find_yarnrc_drift(yarnrc, docs) == []


def test_find_yarnrc_drift_mismatch():
    yarnrc = "yarnPath: .yarn/releases/yarn-3.6.1.cjs\n"
    docs = {"README.md": "This project uses yarn 3.5.0"}
    drifts = find_yarnrc_drift(yarnrc, docs)
    assert len(drifts) == 1
    assert drifts[0]["yarnrc_version"] == "3.6.1"
    assert drifts[0]["doc_version"] == "3.5.0"


def test_find_yarnrc_drift_no_yarnrc():
    assert find_yarnrc_drift(None, {"README.md": "text"}) == []


def test_find_yarnrc_drift_no_version_in_yarnrc():
    yarnrc = "nodeLinker: node-modules\n"
    assert find_yarnrc_drift(yarnrc, {"README.md": "yarn 3.6"}) == []
