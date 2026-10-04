"""Regression tests for issue #474: an explicit ``max_file_size`` of 0.

``scan_repo()`` merged its explicit argument with the config value using ``or``,
so ``max_file_size=0`` -- a limit that means "read nothing" -- was treated as
"caller passed nothing" and replaced by the 1MB default. The value is lost one
layer above ``_read_text_safe``, which honours ``max_size=0`` correctly.

The config path (``max_file_size = 0`` in ``.driftcheck.toml``) was already
honoured, so the two surfaces for the same intent disagreed. These tests pin the
argument path to the config path.
"""
from __future__ import annotations
import tempfile
from pathlib import Path

from driftcheck.detector import scan_repo


def _record_max_sizes(monkeypatch, root: Path, max_file_size):
    """Return the distinct max_size values that reach the file reader."""
    import driftcheck.detector as det

    seen: set = set()
    original = det._read_text_safe

    def spy(path, *args, **kwargs):
        value = kwargs.get("max_size", args[0] if args else None)
        if value is not None:
            seen.add(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(det, "_read_text_safe", spy)
    scan_repo(root, max_file_size=max_file_size)
    monkeypatch.undo()
    return seen


def _repo_with_a_drift(root: Path) -> Path:
    """A tree whose scan finds drift only when files are actually read."""
    (root / "requirements.txt").write_text("requests==2.31.0\n")
    (root / "README.md").write_text("# P\n\nRequires requests 2.30.0.\n")
    (root / ".gitattributes").write_text("* text=auto eol=lf\n")
    return root


class TestExplicitZeroIsNotDropped:
    """The reported defect: `or` cannot tell None from 0."""

    def test_zero_reaches_the_file_reader(self, tmp_path, monkeypatch):
        """max_file_size=0 must reach _read_text_safe, not the 1MB default."""
        _repo_with_a_drift(tmp_path)
        assert _record_max_sizes(monkeypatch, tmp_path, 0) == {0}

    def test_none_reaches_the_file_reader(self, tmp_path, monkeypatch):
        """None still means 'not supplied' and resolves to the 1MB default."""
        _repo_with_a_drift(tmp_path)
        assert _record_max_sizes(monkeypatch, tmp_path, None) == {1_000_000}

    def test_zero_and_none_differ(self, tmp_path, monkeypatch):
        """The two inputs must not collapse to the same downstream value."""
        _repo_with_a_drift(tmp_path)
        zero = _record_max_sizes(monkeypatch, tmp_path, 0)
        nothing = _record_max_sizes(monkeypatch, tmp_path, None)
        assert zero != nothing

    def test_non_zero_override_still_wins(self, tmp_path, monkeypatch):
        """A truthy explicit limit is still honoured (unchanged behaviour)."""
        _repo_with_a_drift(tmp_path)
        assert _record_max_sizes(monkeypatch, tmp_path, 500) == {500}

    def test_zero_reads_nothing_and_finds_no_drift(self, tmp_path):
        """With max_file_size=0 no file is read, so no blocking drift is reported.

        Informational keys such as `dependabot_drifts` still appear: they are
        derived from which files exist, not from reading file contents, so they
        are identical on the config path too (asserted below).
        """
        from driftcheck.cli import INFORMATIONAL_DRIFTS
        _repo_with_a_drift(tmp_path)
        result = scan_repo(tmp_path, max_file_size=0)
        blocking = [
            k for k, v in result.items()
            if v and k.endswith("_drifts") and k not in INFORMATIONAL_DRIFTS
        ]
        assert blocking == []

    def test_config_zero_matches_argument_zero(self, tmp_path):
        """Both surfaces for 'read nothing' must now agree, key for key."""
        _repo_with_a_drift(tmp_path)
        (tmp_path / ".driftcheck.toml").write_text("[driftcheck]\nmax_file_size = 0\n")
        from_config = scan_repo(tmp_path, max_file_size=None)
        from_argument = scan_repo(tmp_path, max_file_size=0)
        assert {
            k: v for k, v in from_config.items() if v and k.endswith("_drifts")
        } == {
            k: v for k, v in from_argument.items() if v and k.endswith("_drifts")
        }

    def test_cli_flag_zero_reads_nothing(self, tmp_path, capsys):
        """`--max-file-size 0` must skip every file, exactly like the config."""
        from driftcheck.cli import main
        _repo_with_a_drift(tmp_path)
        rc = main(["--max-file-size", "0", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "requests 2.30.0" not in out