"""Tests for engines drift detection (package.json engines vs .nvmrc / volta)."""
from driftcheck.detectors.engines import (
    find_engines_drift,
    _parse_node_version,
    _parse_nvmrc,
)


class TestParseNodeVersion:
    def test_full_version(self):
        assert _parse_node_version("20.11.0") == (20, 11, 0)

    def test_major_only(self):
        assert _parse_node_version("20") == (20, 0, 0)

    def test_major_minor(self):
        assert _parse_node_version("20.11") == (20, 11, 0)

    def test_with_prefix_gte(self):
        assert _parse_node_version(">=18") == (18, 0, 0)

    def test_with_prefix_caret(self):
        assert _parse_node_version("^20") == (20, 0, 0)

    def test_with_prefix_tilde(self):
        assert _parse_node_version("~20.11") == (20, 11, 0)

    def test_lts_alias(self):
        assert _parse_node_version("lts/*") is None

    def test_with_v_prefix(self):
        assert _parse_node_version("v20.11.0") == (20, 11, 0)


class TestParseNvmrc:
    def test_full_version(self):
        assert _parse_nvmrc("20.11.0") == "20.11.0"

    def test_major_only(self):
        assert _parse_nvmrc("20") == "20"

    def test_with_v_prefix(self):
        assert _parse_nvmrc("v20.11.0") == "20.11.0"

    def test_lts_alias(self):
        assert _parse_nvmrc("lts/*") is None

    def test_empty(self):
        assert _parse_nvmrc("") is None

    def test_whitespace(self):
        assert _parse_nvmrc("  20.11  ") == "20.11"


class TestFindEnginesDrift:
    def test_no_package_json(self, tmp_path):
        assert find_engines_drift(tmp_path) == []

    def test_no_engines_or_nvmrc(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert find_engines_drift(tmp_path) == []

    def test_matching_engines_and_nvmrc(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "20.11.0"}}')
        (tmp_path / ".nvmrc").write_text("20.11.0")
        assert find_engines_drift(tmp_path) == []

    def test_matching_major_minor(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "20.11.1"}}')
        (tmp_path / ".nvmrc").write_text("20.11.5")
        assert find_engines_drift(tmp_path) == []

    def test_drift_engines_vs_nvmrc(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "18.0.0"}}')
        (tmp_path / ".nvmrc").write_text("20.11.0")
        result = find_engines_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "engines_drift"
        assert "18.0.0" in result[0]["detail"]
        assert "20.11.0" in result[0]["detail"]

    def test_drift_engines_vs_volta(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"engines": {"node": "18.0.0"}, "volta": {"node": "20.11.0"}}'
        )
        result = find_engines_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "engines_drift"
        assert "volta.node" in result[0]["detail"]

    def test_no_drift_with_volta_matching(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"engines": {"node": "20.11.0"}, "volta": {"node": "20.11.5"}}'
        )
        assert find_engines_drift(tmp_path) == []

    def test_only_engines_no_nvmrc(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "20.11.0"}}')
        assert find_engines_drift(tmp_path) == []

    def test_only_nvmrc_no_engines(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / ".nvmrc").write_text("20.11.0")
        assert find_engines_drift(tmp_path) == []

    def test_invalid_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not json")
        assert find_engines_drift(tmp_path) == []
