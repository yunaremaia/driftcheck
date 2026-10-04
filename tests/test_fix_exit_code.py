"""Regression tests for issue #473: `--fix` returned 0 with blocking drifts present.

The ``--fix`` branch sat above the ``all_drifts`` / ``blocking_drifts``
computation and returned 0 on both of its paths, so the one mode whose job is to
change the tree was the one mode reporting success in CI. ``--report``,
``--sarif`` and ``--csv`` already recomputed the same answer correctly, which
made the default text mode the outlier rather than a deliberate policy.
"""
from __future__ import annotations
from pathlib import Path

import pytest


def _repo_with_unfixable_drift(tmp_path: Path) -> Path:
    """README claims requests 2.30.0 while requirements.txt pins 2.31.0.

    This drift is detected but not auto-fixable, which is the case the report
    describes: `--fix` has nothing to do and must still fail the build.
    """
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    (tmp_path / "README.md").write_text("# P\n\nRequires requests 2.30.0.\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    return tmp_path


class TestFixExitCodeAgreesWithOtherModes:
    @pytest.fixture(autouse=True)
    def _quiet(self, capsys):
        self.capsys = capsys

    def test_plain_scan_fails(self, tmp_path):
        from driftcheck.cli import main
        _repo_with_unfixable_drift(tmp_path)
        assert main([str(tmp_path)]) == 1

    @pytest.mark.parametrize("flag", [[], ["--json"]])
    def test_fix_exits_1_with_blocking_drifts(self, tmp_path, flag):
        from driftcheck.cli import main
        _repo_with_unfixable_drift(tmp_path)
        assert main(["--fix", *flag, str(tmp_path)]) == 1

    @pytest.mark.parametrize("flag", [["--report"], ["--sarif"], ["--csv"]])
    def test_fix_agrees_with_machine_modes(self, tmp_path, flag):
        """--fix must return exactly what the same tree returns without --fix."""
        from driftcheck.cli import main
        _repo_with_unfixable_drift(tmp_path)
        without = main([*flag, str(tmp_path)])
        self.capsys.readouterr()
        with_fix = main(["--fix", *flag, str(tmp_path)])
        assert with_fix == without == 1

    def test_fix_reports_nothing_to_fix(self, tmp_path):
        from driftcheck.cli import main
        _repo_with_unfixable_drift(tmp_path)
        main(["--fix", str(tmp_path)])
        assert "no drifts to fix" in self.capsys.readouterr().out

    def test_fix_exits_0_on_a_clean_tree(self, tmp_path):
        """A clean tree stays 0 -- the fix must not invent failures."""
        from driftcheck.cli import main
        (tmp_path / "README.md").write_text("# P\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        assert main(["--fix", str(tmp_path)]) == 0

    def test_fix_exits_0_when_it_fixed_everything(self, tmp_path):
        """A drift `--fix` actually repairs must not keep failing the build."""
        from driftcheck.cli import main
        (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.75.0"\n')
        (tmp_path / "README.md").write_text("# P\n\nRust 1.70.0\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        assert main([str(tmp_path)]) == 1, "fixture must start with a blocking drift"
        self.capsys.readouterr()
        assert main(["--fix", str(tmp_path)]) == 0
        assert "1.75.0" in (tmp_path / "README.md").read_text()