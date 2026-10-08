"""Tests for Renovate drift detection."""

from __future__ import annotations
import json

from driftcheck.detectors import find_renovate_drift


def test_no_renovate_file(temp_empty_repo):
    """No renovate.json → no drifts."""
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 0


def test_renovate_no_package_rules(temp_empty_repo):
    """renovate.json without packageRules → informational drift."""
    (temp_empty_repo / "renovate.json").write_text(json.dumps({
        "extends": ["config:base"],
    }))
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    d = drifts[0]
    assert d["drift_key"] == "renovate_no_package_rules"
    assert d["severity"] == "informational"
    assert d["file"] == "renovate.json"


def test_renovate_with_package_rules(temp_empty_repo):
    """renovate.json with packageRules → no drift."""
    (temp_empty_repo / "renovate.json").write_text(json.dumps({
        "extends": ["config:base"],
        "packageRules": [
            {"matchManagers": ["npm"], "enabled": True},
        ],
    }))
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 0


def test_renovate_enabled_false(temp_empty_repo):
    """renovate.json with enabled: false → informational."""
    (temp_empty_repo / "renovate.json").write_text(json.dumps({
        "enabled": False,
        "packageRules": [{"matchManagers": ["npm"], "enabled": True}],
    }))
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    assert drifts[0]["drift_key"] == "renovate_disabled"


def test_renovate_blocking_manager_policy(temp_empty_repo):
    """managerPolicy blocking all updates → informational."""
    (temp_empty_repo / "renovate.json").write_text(json.dumps({
        "extends": ["config:base"],
        "packageRules": [{"matchManagers": ["npm"], "enabled": True}],
        "managerPolicy": [
            {"match": {"matchManagers": ".*", "updateTypes": ["none"]}},
        ],
    }))
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    assert drifts[0]["drift_key"] == "renovate_blocking_policy"


def test_renovate_json5_format(temp_empty_repo):
    """renovate.json5 is also detected."""
    (temp_empty_repo / "renovate.json5").write_text("""
{
  "extends": ["config:base"]
}
""")
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    assert drifts[0]["file"] == "renovate.json5"


def test_renovate_parse_error(temp_empty_repo):
    """Invalid JSON → parse error drift."""
    (temp_empty_repo / "renovate.json").write_text("not json")
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    assert drifts[0]["drift_key"] == "renovate_parse_error"
    assert drifts[0]["severity"] == "informational"


def test_renovate_not_object(temp_empty_repo):
    """JSON array instead of object → invalid format drift."""
    (temp_empty_repo / "renovate.json").write_text("[]")
    drifts = find_renovate_drift(temp_empty_repo)
    assert len(drifts) == 1
    assert drifts[0]["drift_key"] == "renovate_invalid_format"
