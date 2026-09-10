"""Tests for tool-versions drift detection: .tool-versions (asdf/mise) vs README."""
from __future__ import annotations
from driftcheck.detectors.tool_versions import (
    parse_tool_versions,
    find_tool_versions_drift,
    TOOL_VERSION_RE,
    TOOL_PATTERNS,
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

    def test_with_v_prefix(self):
        text = "node v20.12.0"
        result = parse_tool_versions(text)
        assert result == {"node": "v20.12.0"}

    def test_major_only(self):
        text = "node 20"
        result = parse_tool_versions(text)
        assert result == {"node": "20"}

    def test_major_minor(self):
        text = "python 3.12"
        result = parse_tool_versions(text)
        assert result == {"python": "3.12"}


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

    def test_whitespace_only(self):
        assert find_tool_versions_drift("  \n  ", {"README.md": "Node 20"}) == []

    def test_multiple_tools(self):
        tv = "node 20.12.0\npython 3.12.0"
        docs = {"README.md": "Node 18 and Python 3.11"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 2

    def test_patch_difference_ignored(self):
        tv = "node 20.12.0"
        docs = {"README.md": "Node.js 20.12.5"}
        assert find_tool_versions_drift(tv, docs) == []

    def test_major_only_in_tool_versions(self):
        tv = "node 20"
        docs = {"README.md": "Node.js 18.0.0"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "node"

    def test_major_only_drift(self):
        tv = "node 20"
        docs = {"README.md": "Node.js 20.12.0"}
        # "20" vs "20.12.0" -> padded to "20.0" vs "20.12.0" -> minor differs
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1

    def test_go_drift(self):
        tv = "go 1.23"
        docs = {"README.md": "Build with Go 1.22"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "go"

    def test_rust_drift(self):
        tv = "rust 1.96.0"
        docs = {"README.md": "Rust 1.95.0 required"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "rust"

    def test_ruby_drift(self):
        tv = "ruby 3.2"
        docs = {"README.md": "Ruby 3.1"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "ruby"

    def test_java_drift(self):
        tv = "java 17"
        docs = {"README.md": "Java 11"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "java"

    def test_php_drift(self):
        tv = "php 8.2"
        docs = {"README.md": "PHP 8.1"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "php"

    def test_dotnet_drift(self):
        tv = "dotnet 8.0"
        docs = {"README.md": ".NET 7.0"}
        result = find_tool_versions_drift(tv, docs)
        assert len(result) == 1
        assert result[0]["tool"] == "dotnet"

    def test_unknown_tool(self):
        tv = "elixir 1.15"
        docs = {"README.md": "Elixir 1.14"}
        # elixir is not in TOOL_PATTERNS, so no drift detected
        result = find_tool_versions_drift(tv, docs)
        assert result == []

    def test_empty_docs(self):
        tv = "node 20.12.0"
        assert find_tool_versions_drift(tv, {}) == []


class TestToolVersionRe:
    def test_match_standard(self):
        m = TOOL_VERSION_RE.search("node 20.12.0")
        assert m is not None
        assert m.group("tool") == "node"
        assert m.group("version") == "20.12.0"

    def test_match_major_only(self):
        m = TOOL_VERSION_RE.search("node 20")
        assert m is not None
        assert m.group("version") == "20"

    def test_match_word_with_space(self):
        # \S+ matches any non-whitespace, so "# comment" matches as tool="#" version="comment"
        m = TOOL_VERSION_RE.search("# comment")
        assert m is not None
        assert m.group("tool") == "#"
        assert m.group("version") == "comment"


class TestToolPatterns:
    def test_node_pattern(self):
        pat = TOOL_PATTERNS["node"]
        m = pat.search("Node.js 20.12.0")
        assert m is not None
        assert m.group(1) == "20.12.0"

    def test_python_pattern(self):
        pat = TOOL_PATTERNS["python"]
        m = pat.search("Python 3.12.0")
        assert m is not None
        assert m.group(1) == "3.12.0"

    def test_go_pattern(self):
        pat = TOOL_PATTERNS["go"]
        m = pat.search("Go 1.23")
        assert m is not None
        assert m.group(1) == "1.23"

    def test_rust_pattern(self):
        pat = TOOL_PATTERNS["rust"]
        m = pat.search("Rust 1.96.0")
        assert m is not None
        assert m.group(1) == "1.96.0"

    def test_ruby_pattern(self):
        pat = TOOL_PATTERNS["ruby"]
        m = pat.search("Ruby 3.2")
        assert m is not None
        assert m.group(1) == "3.2"

    def test_java_pattern(self):
        pat = TOOL_PATTERNS["java"]
        m = pat.search("Java 17")
        assert m is not None
        assert m.group(1) == "17"

    def test_php_pattern(self):
        pat = TOOL_PATTERNS["php"]
        m = pat.search("PHP 8.2")
        assert m is not None
        assert m.group(1) == "8.2"

    def test_dotnet_pattern(self):
        pat = TOOL_PATTERNS["dotnet"]
        m = pat.search(".NET 8.0")
        assert m is not None
        assert m.group(1) == "8.0"
