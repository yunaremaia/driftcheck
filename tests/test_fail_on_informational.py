"""Tests for --fail-on-informational CLI flag (issue #144)."""
from pathlib import Path
from driftcheck.cli import main


class TestFailOnInformational:
    """Tests that --fail-on-informational promotes informational drifts to blocking."""

    def test_without_flag_informational_pass(self, tmp_path):
        """Without flag, informational drifts do not cause failure."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}, "dependencies": {"lodash": "^4.0.0"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\nlodash 4.17.0\n")
        (tmp_path / "package-lock.json").write_text("{}")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main([str(tmp_path)])
        assert result == 0  # no blocking drifts, only informational

    def test_with_flag_informational_fails(self, tmp_path):
        """With --fail-on-informational, informational drifts cause exit 1."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}, "dependencies": {"lodash": "^4.0.0"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\nlodash 4.17.0\n")
        (tmp_path / "package-lock.json").write_text("{}")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main(["--fail-on-informational", str(tmp_path)])
        assert result == 1  # lockfile informational drift promoted to blocking

    def test_no_drifts_still_pass(self, tmp_path):
        """With --fail-on-informational but no drifts, exit 0."""
        (tmp_path / "README.md").write_text("Hello\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main(["--fail-on-informational", str(tmp_path)])
        assert result == 0

    def test_report_flag_with_fail_on_informational(self, tmp_path, capsys):
        """--report --fail-on-informational exits 1 on informational drifts."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main(["--report", "--fail-on-informational", str(tmp_path)])
        # With --fail-on-informational, lockfile drift is promoted
        assert result == 1

    def test_json_flag_with_fail_on_informational(self, tmp_path, capsys):
        """--json --fail-on-informational exits 1 on informational drifts."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main(["--json", "--fail-on-informational", str(tmp_path)])
        assert result == 1


class TestFailOnInformationalConfig:
    """Tests that .driftcheck.toml fail_on_informational is respected."""

    def test_config_option_enables_flag(self, tmp_path):
        """fail_on_informational = true in config behaves like --fail-on-informational."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nfail_on_informational = true\n"
        )
        result = main([str(tmp_path)])
        assert result == 1

    def test_config_option_false_default(self, tmp_path):
        """fail_on_informational = false (default) does not promote."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "engines": {"node": ">=20"}}'
        )
        (tmp_path / "README.md").write_text("Node 20\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = main([str(tmp_path)])
        assert result == 0
