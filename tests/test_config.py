"""Tests for .driftcheck.toml configuration loading."""
from __future__ import annotations
import tempfile
from pathlib import Path

from driftcheck.config import load_config, get_excluded_detectors, _parse_toml


class TestParseToml:
    def test_empty(self):
        assert _parse_toml("") == {}

    def test_comments_only(self):
        assert _parse_toml("# comment\n") == {}

    def test_simple_key_value(self):
        result = _parse_toml('name = "test"')
        assert result == {"name": "test"}

    def test_boolean(self):
        result = _parse_toml("verbose = true\ndebug = false")
        assert result == {"verbose": True, "debug": False}

    def test_list(self):
        result = _parse_toml('exclude = ["node", "python"]')
        assert result == {"exclude": ["node", "python"]}

    def test_section(self):
        text = "[driftcheck]\nexclude = [\"node\"]\nverbose = true"
        result = _parse_toml(text)
        assert result == {"driftcheck": {"exclude": ["node"], "verbose": True}}


class TestLoadConfig:
    def test_no_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(Path(td))
            assert config["exclude_detectors"] == []

    def test_exclude_rust_detector(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\nexclude_detectors = ["rust"]\n'
            )
            config = load_config(root)
            excluded = get_excluded_detectors(config)
            # "rust" maps to both "drifts" and "rust_drifts"
            assert excluded == {"drifts", "rust_drifts"}

    def test_fail_on_informational(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\nfail_on_informational = true\n'
            )
            config = load_config(root)
            assert config["fail_on_informational"] is True

    def test_with_scan_repo(self):
        """Test that scan_repo reads and applies .driftcheck.toml config."""
        from driftcheck.detector import scan_repo
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Set up a repo with both rust and node
            (root / "rust-toolchain.toml").write_text('channel = "1.96.1"')
            (root / "package.json").write_text('{"engines": {"node": "24.x"}}')
            (root / "README.md").write_text("Rust 1.96.1 and Node 24")
            # Exclude rust detector
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\nexclude_detectors = ["rust"]\n'
            )
            result = scan_repo(root)
            # drifts should be excluded
            assert "drifts" not in result
            # node drifts should still be present
            assert "node_drifts" in result
