"""Tests for .driftcheck.toml configuration loading."""
from __future__ import annotations
import tempfile
from pathlib import Path

import pytest

try:  # Python 3.11+ stdlib
    import tomllib
except ImportError:  # Python 3.10 backport
    import tomli as tomllib  # type: ignore[no-redef]

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


class TestParseTomlInlineComments:
    """Regression tests for issue #143.

    A hand-rolled parser treated `value # note` as part of the value, so a
    commented-out list arrived as a bare string and silently disabled the
    exclusions the user asked for.
    """

    def test_inline_comment_after_list(self):
        text = '[driftcheck]\nexclude_detectors = ["node", "rust"] # skip these\n'
        result = _parse_toml(text)
        assert result == {"driftcheck": {"exclude_detectors": ["node", "rust"]}}

    def test_inline_comment_after_scalar(self):
        text = "[driftcheck]\nfollow_symlinks = false # no links in CI\n"
        result = _parse_toml(text)
        assert result == {"driftcheck": {"follow_symlinks": False}}

    def test_hash_inside_quoted_string_is_preserved(self):
        text = '[driftcheck]\ndoc_paths = ["docs/a#b.md"]\n'
        result = _parse_toml(text)
        assert result == {"driftcheck": {"doc_paths": ["docs/a#b.md"]}}

    def test_full_line_comment_inside_section(self):
        text = '[driftcheck]\n# doc_paths = ["nope.md"]\nmax_file_size = 500\n'
        result = _parse_toml(text)
        assert result == {"driftcheck": {"max_file_size": 500}}


class TestParseTomlMultilineArrays:
    """Regression tests for issue #143: arrays split across lines."""

    def test_multiline_array(self):
        text = '[driftcheck]\nexclude_detectors = [\n  "node",\n  "rust",\n]\n'
        result = _parse_toml(text)
        assert result == {"driftcheck": {"exclude_detectors": ["node", "rust"]}}

    def test_multiline_array_with_trailing_inline_comment(self):
        text = '[driftcheck]\ndoc_paths = [\n  "README.md",\n  "docs/setup.md",\n] # extra docs\n'
        result = _parse_toml(text)
        assert result == {"driftcheck": {"doc_paths": ["README.md", "docs/setup.md"]}}


class TestLoadConfigToml:
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
            # "rust" maps to "rust_drifts"
            assert excluded == {"rust_drifts"}

    def test_fail_on_informational(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\nfail_on_informational = true\n'
            )
            config = load_config(root)
            assert config["fail_on_informational"] is True

    def test_exclusions_survive_an_inline_comment(self):
        """Issue #143: a trailing comment used to turn the list into a string."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\nexclude_detectors = ["rust", "node"] # slow in CI\n'
            )
            config = load_config(root)
            assert config["exclude_detectors"] == ["rust", "node"]
            assert get_excluded_detectors(config) == {"rust_drifts", "node_drifts"}

    def test_exclusions_survive_a_multiline_array(self):
        """Issue #143: an array with `]` on its own line parsed as a string."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                "[driftcheck]\nexclude_detectors = [\n  \"rust\",\n  \"node\",\n]\n"
            )
            config = load_config(root)
            assert get_excluded_detectors(config) == {"rust_drifts", "node_drifts"}

    def test_doc_paths_with_a_hash_survive(self):
        """Issue #143: `#` inside a quoted string must not start a comment."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[driftcheck]\ndoc_paths = ["docs/a#b.md"]\n'
            )
            config = load_config(root)
            assert config["doc_paths"] == ["docs/a#b.md"]

    def test_invalid_toml_reports_the_error_instead_of_parsing_garbage(self):
        """A malformed config must surface, not silently yield a half-parsed dict."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text("this is not valid toml [[[")
            with pytest.raises(tomllib.TOMLDecodeError):
                load_config(root)

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
            # rust_drifts should be excluded (not in result)
            assert "rust_drifts" not in result
            # node drifts should still be present
            assert "node_drifts" in result


class TestLoadConfigTopLevelKeys:
    """Top-level keys must be honoured, not silently dropped.

    `load_config` flattened top-level keys with `if k not in cfg`, but `cfg`
    is pre-seeded from DEFAULT_CONFIG, so that condition was False for every
    key that has a default. A documented top-level `exclude_detectors` was
    therefore ignored while the same key under [driftcheck] worked: a silent
    misconfiguration where the requested exclusion has no effect and the
    drift the user wanted suppressed is still reported.
    """

    def test_top_level_exclude_detectors_is_honored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text('exclude_detectors = ["node"]\n')
            config = load_config(root)
            assert config["exclude_detectors"] == ["node"]
            assert get_excluded_detectors(config) == {"node_drifts"}

    def test_top_level_scalar_overrides_a_default(self):
        """A defaulted scalar must be overridable at top level too."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                "follow_symlinks = false\nmax_file_size = 500\n"
            )
            config = load_config(root)
            assert config["follow_symlinks"] is False
            assert config["max_file_size"] == 500

    def test_driftcheck_section_still_wins_over_top_level(self):
        """Precedence rule: [driftcheck] overrides the same top-level key."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                'exclude_detectors = ["node"]\n\n[driftcheck]\nexclude_detectors = ["rust"]\n'
            )
            config = load_config(root)
            assert config["exclude_detectors"] == ["rust"]
            assert get_excluded_detectors(config) == {"rust_drifts"}

    def test_unknown_top_level_scalar_key_is_accepted(self):
        """Preserved behaviour: a key with no default is still picked up."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text("unknown_knob = 42\n")
            config = load_config(root)
            assert config["unknown_knob"] == 42

    def test_foreign_toml_table_does_not_leak_into_config(self):
        """A non-driftcheck table is not config; it must not land in cfg."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".driftcheck.toml").write_text(
                '[tool.example]\nname = "x"\n\n[something-else]\nk = 1\n'
            )
            config = load_config(root)
            assert "tool" not in config
            assert "something-else" not in config
            assert not [k for k, v in config.items() if isinstance(v, dict)]

    def test_top_level_exclusion_reaches_scan_repo(self):
        """End-to-end: the top-level exclusion actually suppresses the drift."""
        from driftcheck.detector import scan_repo
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rust-toolchain.toml").write_text('channel = "1.96.1"')
            (root / "package.json").write_text('{"engines": {"node": "24.x"}}')
            (root / "README.md").write_text("Rust 1.96.1 and Node 24")
            (root / ".driftcheck.toml").write_text('exclude_detectors = ["rust"]\n')
            result = scan_repo(root)
            assert "rust_drifts" not in result
            assert "node_drifts" in result

