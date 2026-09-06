"""Tests for tool-versions and nvmrc detectors."""
from pathlib import Path
import tempfile
import os

from driftcheck.detectors.tool_versions import (
    parse_tool_versions,
    find_tool_versions_drift,
)
from driftcheck.detectors.nvmrc import (
    parse_nvmrc_version,
    find_nvmrc_drift,
)


class TestParseToolVersions:
    def test_empty(self):
        assert parse_tool_versions("") == {}

    def test_single(self):
        assert parse_tool_versions("node 20.12.0") == {"node": "20.12.0"}

    def test_multiple(self):
        text = "node 20.12.0\npython 3.12.0\ngo 1.23"
        result = parse_tool_versions(text)
        assert result == {"node": "20.12.0", "python": "3.12.0", "go": "1.23"}

    def test_comments_ignored(self):
        text = "# comment\nnode 20.12.0\n# another\npython 3.12.0"
        result = parse_tool_versions(text)
        assert "# comment" not in result
        assert result["node"] == "20.12.0"
        assert result["python"] == "3.12.0"


class TestFindToolVersionsDrift:
    def test_no_drift(self):
        tv = "node 20.12.0"
        docs = {"README.md": "This project uses Node.js 20.12.0"}
        assert find_tool_versions_drift(tv, docs) == []

    def test_drift_major(self):
        tv = "node 20.12.0"
        docs = {"README.md": "This project uses Node.js 18.0.0"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "node"
        assert result[0]["doc_version"] == "18.0.0"
        assert result[0]["tool_versions_version"] == "20.12.0"

    def test_drift_minor(self):
        tv = "python 3.12.0"
        docs = {"README.md": "Python 3.11.0 required"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "python"

    def test_empty_tool_versions(self):
        assert find_tool_versions_drift("", {"README.md": "Node 20"}) == []

    def test_multiple_tools(self):
        tv = "node 20.12.0\npython 3.12.0"
        docs = {"README.md": "Node 18 and Python 3.11"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 2

    def test_patch_difference_ignored(self):
        tv = "node 20.12.0"
        docs = {"README.md": "Node.js 20.12.5"}
        assert find_tool_versions_drift(tv, docs) == []


class TestParseNvmrcVersion:
    def test_simple(self):
        assert parse_nvmrc_version("20.12.0") == "20.12.0"

    def test_major_only(self):
        assert parse_nvmrc_version("20") == "20"

    def test_with_v_prefix(self):
        # parse_nvmrc_version strips leading 'v'
        assert parse_nvmrc_version("v20.12.0") == "20.12.0"

    def test_empty(self):
        assert parse_nvmrc_version("") is None

    def test_whitespace(self):
        assert parse_nvmrc_version("  20.12.0  ") == "20.12.0"


class TestFindNvmrcDrift:
    def test_no_drift(self):
        nvmrc = "20.12.0"
        pkg = ">=20.12.0"
        docs = {}
        assert find_nvmrc_drift(nvmrc, pkg, docs) == []

    def test_drift_vs_package(self):
        nvmrc = "18.0.0"
        pkg = ">=20.12.0"
        docs = {}
        result = find_nvmrc_drift(nvmrc, pkg, docs)
        assert len(result) == 1
        assert result[0]["nvmrc_version"] == "18.0.0"
        assert result[0]["package_version"] == ">=20.12.0"

    def test_drift_vs_docs(self):
        nvmrc = "20.12.0"
        pkg = None
        docs = {"README.md": "Node.js 18.0.0"}
        result = find_nvmrc_drift(nvmrc, pkg, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "18.0.0"

    def test_empty_nvmrc(self):
        assert find_nvmrc_drift("", "20.12.0", {"README.md": "Node 18"}) == []

    def test_patch_difference_ignored(self):
        nvmrc = "20.12.0"
        pkg = ">=20.12.5"
        docs = {}
        assert find_nvmrc_drift(nvmrc, pkg, docs) == []

    def test_single_number_version(self):
        nvmrc = "20"
        pkg = ">=20.12.0"
        docs = {}
        assert find_nvmrc_drift(nvmrc, pkg, docs) == []
