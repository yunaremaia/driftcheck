"""Tests for mise.toml drift detection."""
from driftcheck.detectors.mise import (
    parse_mise_tools,
    find_mise_drift,
)


class TestParseMiseTools:
    def test_plain_string_specs(self):
        text = '[tools]\nnode = "22.1.0"\npython = "3.12.0"\n'
        result = parse_mise_tools(text)
        assert result == {"node": "22.1.0", "python": "3.12.0"}

    def test_dict_spec_with_version(self):
        text = '[tools]\npython = {version = "3.12", virtualenv = ".venv"}\n'
        result = parse_mise_tools(text)
        assert result == {"python": "3.12"}

    def test_mixed_specs(self):
        text = '[tools]\nnode = "20.0.0"\nrust = {version = "1.78"}\ngo = "1.22"\n'
        result = parse_mise_tools(text)
        assert result == {"node": "20.0.0", "rust": "1.78", "go": "1.22"}

    def test_empty_tools_section(self):
        text = "[tools]\n"
        result = parse_mise_tools(text)
        assert result == {}

    def test_no_tools_section(self):
        text = "[settings]\nexperimental = true\n"
        result = parse_mise_tools(text)
        assert result == {}

    def test_invalid_toml(self):
        text = "not valid toml [[["
        result = parse_mise_tools(text)
        assert result == {}

    def test_dict_spec_without_version(self):
        text = '[tools]\nnode = {foo = "bar"}\n'
        result = parse_mise_tools(text)
        assert result == {}


class TestFindMiseDrift:
    def test_detects_drift(self):
        mise = '[tools]\nnode = "22.1.0"\n'
        docs = {"README.md": "This project uses Node.js 21.0.0"}
        drifts = find_mise_drift(mise, docs)
        assert len(drifts) == 1
        assert drifts[0]["tool"] == "node"
        assert drifts[0]["doc_version"] == "21.0.0"
        assert drifts[0]["mise_version"] == "22.1.0"

    def test_no_drift(self):
        mise = '[tools]\npython = "3.12.0"\n'
        docs = {"README.md": "Built with Python 3.12"}
        drifts = find_mise_drift(mise, docs)
        assert len(drifts) == 0

    def test_empty_mise(self):
        drifts = find_mise_drift("", {"README.md": "hello"})
        assert drifts == []

    def test_tool_without_pattern(self):
        mise = '[tools]\nnonexistenttool = "1.0.0"\n'
        docs = {"README.md": "Uses nonexistenttool 1.0.0"}
        drifts = find_mise_drift(mise, docs)
        assert drifts == []

    def test_normalizes_leading_v(self):
        mise = '[tools]\nnode = "v22.0.0"\n'
        docs = {"README.md": "node v21"}
        drifts = find_mise_drift(mise, docs)
        assert len(drifts) == 1
