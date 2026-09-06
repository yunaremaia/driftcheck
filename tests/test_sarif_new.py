"""Tests for SARIF output with new drift types."""
from __future__ import annotations
import json

from driftcheck.sarif import to_sarif


def test_sarif_tool_versions_drift():
    result = {
        "tool_versions_drifts": [
            {
                "file": "README.md",
                "tool": "node",
                "doc_version": "18.0.0",
                "tool_versions_version": "20.12.0",
                "pos": 0,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.25")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "tool-versions-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "tool-versions-drift"
    assert "20.12.0" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_nvmrc_drift_informational():
    result = {
        "nvmrc_drifts": [
            {
                "file": ".nvmrc",
                "doc_version": "18.0.0",
                "nvmrc_version": "18.0.0",
                "package_version": ">=20.12.0",
                "pos": 0,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.25")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "nvmrc-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    # nvmrc is informational → SARIF level: warning
    assert results[0]["level"] == "warning"
