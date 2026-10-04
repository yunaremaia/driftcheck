"""Regression tests for issue #469: `--fail-on-informational` does not exist.

The README documents both the config key `fail_on_informational` and the
`--fail-on-informational` flag. The flag was implemented in #218 and then removed
by a documentation commit (07e30ba) that rewrote cli.py, config.py and
detector.py; the README section was never reverted with it. The config key stayed
in `DEFAULT_CONFIG`, so the TOML parser accepts it and nothing reads it --
"parse but never apply", the exact failure class #144/#209/#220 were filed for.

An operator following the README got a silently ignored key, so the fix restores
both surfaces.
"""
from __future__ import annotations
from pathlib import Path

import pytest


def _repo_with_informational_only(tmp_path: Path) -> Path:
    """requirements.txt with no lockfile: reported, informational, non-blocking."""
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    (tmp_path / "README.md").write_text("# P\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    return tmp_path


class TestFailOnInformationalFlag:
    def test_flag_is_accepted(self, tmp_path):
        """The documented flag must parse instead of exiting 2."""
        from driftcheck.cli import main
        _repo_with_informational_only(tmp_path)
        assert main(["--fail-on-informational", str(tmp_path)]) in (0, 1)

    def test_flag_appears_in_help(self, capsys):
        from driftcheck.cli import main
        with pytest.raises(SystemExit):
            main(["--help"])
        assert "fail-on-informational" in capsys.readouterr().out

    def test_flag_makes_informational_blocking(self, tmp_path):
        """With the flag, a tree that only has informational drifts exits 1."""
        from driftcheck.cli import main
        _repo_with_informational_only(tmp_path)
        assert main([str(tmp_path)]) == 0, "fixture must be clean by default"
        assert main(["--fail-on-informational", str(tmp_path)]) == 1


class TestFailOnInformationalConfig:
    def test_config_key_is_honoured(self, tmp_path):
        """fail_on_informational = true must fail the build like the flag."""
        from driftcheck.cli import main
        _repo_with_informational_only(tmp_path)
        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nfail_on_informational = true\n"
        )
        assert main([str(tmp_path)]) == 1

    def test_config_false_leaves_them_informational(self, tmp_path):
        from driftcheck.cli import main
        _repo_with_informational_only(tmp_path)
        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nfail_on_informational = false\n"
        )
        assert main([str(tmp_path)]) == 0

    def test_flag_overrides_config_false(self, tmp_path):
        from driftcheck.cli import main
        _repo_with_informational_only(tmp_path)
        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nfail_on_informational = false\n"
        )
        assert main(["--fail-on-informational", str(tmp_path)]) == 1

    def test_default_is_off(self):
        from driftcheck.config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["fail_on_informational"] is False