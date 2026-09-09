"""Tests for npmrc drift detection."""
import pytest
from driftcheck.detectors.npmrc import (
    parse_npmrc,
    find_npmrc_drift,
)


def test_parse_npmrc_basic():
    text = "registry=https://registry.npmjs.org/\nsave-exact=true\n"
    result = parse_npmrc(text)
    assert result == {"registry": "https://registry.npmjs.org/", "save-exact": "true"}


def test_parse_npmrc_quoted():
    text = 'registry="https://registry.npmjs.org/"\n'
    result = parse_npmrc(text)
    assert result == {"registry": "https://registry.npmjs.org/"}


def test_parse_npmrc_with_comments():
    text = "# This is a comment\nregistry=https://registry.npmjs.org/\n; another comment\n"
    result = parse_npmrc(text)
    assert result == {"registry": "https://registry.npmjs.org/"}


def test_parse_npmrc_empty():
    assert parse_npmrc("") == {}


def test_parse_npmrc_no_registry():
    text = "save-exact=true\n"
    result = parse_npmrc(text)
    assert result == {"save-exact": "true"}


def test_parse_npmrc_engine_strict():
    text = "engine-strict=true\n"
    result = parse_npmrc(text)
    assert result == {"engine-strict": "true"}


def test_find_npmrc_drift_no_drift():
    npmrc = "registry=https://registry.npmjs.org/\n"
    pkg_json = '{"engines": {"node": ">=20"}}'
    docs = {"README.md": "Use Node.js 20"}
    assert find_npmrc_drift(npmrc, pkg_json, docs) == []


def test_find_npmrc_drift_engine_strict_no_engines():
    npmrc = "engine-strict=true\n"
    pkg_json = '{"name": "test"}'
    docs = {"README.md": "No engines mentioned"}
    drifts = find_npmrc_drift(npmrc, pkg_json, docs)
    assert len(drifts) == 1
    assert "engine-strict=true" in drifts[0]["detail"]


def test_find_npmrc_drift_no_npmrc():
    assert find_npmrc_drift(None, '{"name": "test"}', {"README.md": "text"}) == []


def test_find_npmrc_drift_no_registry_in_npmrc():
    npmrc = "save-exact=true\n"
    assert find_npmrc_drift(npmrc, '{"name": "test"}', {"README.md": "text"}) == []


def test_find_npmrc_drift_registry_mismatch():
    npmrc = "registry=https://registry.npmjs.org/\n"
    pkg_json = '{"publishConfig": {"registry": "https://private.registry.com/"}}'
    docs = {"README.md": "Use our private registry"}
    drifts = find_npmrc_drift(npmrc, pkg_json, docs)
    assert len(drifts) == 1
    assert "registry" in drifts[0]["detail"]


def test_find_npmrc_drift_tag_version_prefix():
    npmrc = "tag-version-prefix=version-\n"
    pkg_json = '{"name": "test"}'
    docs = {"README.md": "We use version- prefix"}
    drifts = find_npmrc_drift(npmrc, pkg_json, docs)
    assert len(drifts) == 1
    assert "tag-version-prefix" in drifts[0]["detail"]


def test_parse_npmrc_registry_alias():
    """Test backward compatibility alias."""
    from driftcheck.detectors.npmrc import parse_npmrc_registry
    text = "registry=https://registry.npmjs.org/\n"
    assert parse_npmrc_registry(text) == {"registry": "https://registry.npmjs.org/"}
