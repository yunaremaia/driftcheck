"""Tests for npmrc drift detection."""
import pytest
from driftcheck.detectors.npmrc import (
    parse_npmrc_registry,
    find_npmrc_drift,
)


def test_parse_npmrc_registry_basic():
    text = "registry=https://registry.npmjs.org/\n"
    assert parse_npmrc_registry(text) == "https://registry.npmjs.org/"


def test_parse_npmrc_registry_quoted():
    text = 'registry="https://registry.npmjs.org/"\n'
    assert parse_npmrc_registry(text) == "https://registry.npmjs.org/"


def test_parse_npmrc_registry_with_comments():
    text = "# This is a comment\nregistry=https://registry.npmjs.org/\n"
    assert parse_npmrc_registry(text) == "https://registry.npmjs.org/"


def test_parse_npmrc_registry_empty():
    assert parse_npmrc_registry("") is None


def test_parse_npmrc_registry_no_registry():
    text = "save-exact=true\n"
    assert parse_npmrc_registry(text) is None


def test_find_npmrc_drift_no_drift():
    npmrc = "registry=https://registry.npmjs.org/\n"
    docs = {"README.md": "Our registry is https://registry.npmjs.org/"}
    assert find_npmrc_drift(npmrc, docs) == []


def test_find_npmrc_drift_mismatch():
    npmrc = "registry=https://registry.npmjs.org/\n"
    docs = {"README.md": "Use https://private.registry.example.com/ for packages"}
    drifts = find_npmrc_drift(npmrc, docs)
    assert len(drifts) == 1
    assert drifts[0]["npmrc_registry"] == "https://registry.npmjs.org/"
    assert drifts[0]["doc_registry"] == "https://private.registry.example.com/"


def test_find_npmrc_drift_no_npmrc():
    assert find_npmrc_drift(None, {"README.md": "text"}) == []


def test_find_npmrc_drift_no_registry_in_npmrc():
    npmrc = "save-exact=true\n"
    assert find_npmrc_drift(npmrc, {"README.md": "text"}) == []
