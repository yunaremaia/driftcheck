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


def test_sarif_swift_drift():
    result = {
        "swift_drifts": [
            {
                "file": "README.md",
                "doc_version": "5.7",
                "package_version": "5.9",
                "pos": 18,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.25")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "swift-package-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "swift-package-version-drift"
    assert "5.9" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_elixir_drift():
    result = {
        "elixir_drifts": [
            {
                "file": "README.md",
                "doc_version": "1.14",
                "mix_version": "1.15",
                "pos": 10,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.31")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "elixir-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "elixir-version-drift"
    assert "1.15" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_cmake_drift():
    result = {
        "cmake_drifts": [
            {
                "file": "README.md",
                "doc_version": "3.16",
                "cmake_version": "3.20",
                "pos": 10,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.31")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "cmake-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "cmake-version-drift"
    assert "3.20" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_requirements_drift():
    result = {
        "requirements_drifts": [
            {
                "file": "README.md",
                "package": "requests",
                "doc_version": "2.25.0",
                "requirements_version": "2.28.0",
                "pos": 10,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.32")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "requirements-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "requirements-version-drift"
    assert "requests" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_kotlin_drift():
    result = {
        "kotlin_drifts": [
            {
                "file": "README.md",
                "doc_version": "1.8.0",
                "gradle_version": "1.9.0",
                "pos": 10,
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.32")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "kotlin-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "kotlin-version-drift"
    assert "1.9.0" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_pipfile_drift():
    result = {
        "pipfile_drifts": [
            {
                "file": "Pipfile",
                "package": "flask",
                "pipfile_version": "==2.0.0",
                "lock_version": "==2.0.1",
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.32")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "pipfile-version-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "pipfile-version-drift"
    assert "flask" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"


def test_sarif_conda_drift():
    result = {
        "conda_drifts": [
            {
                "file": "environment.yml",
                "package": "numpy",
                "environment_version": "unpinned",
            }
        ]
    }
    sarif = to_sarif(result, version="0.1.32")
    rules = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "conda-unpinned-drift" in rules
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "conda-unpinned-drift"
    assert "numpy" in results[0]["message"]["text"]
    assert results[0]["level"] == "error"
