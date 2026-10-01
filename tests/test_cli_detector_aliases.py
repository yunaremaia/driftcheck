"""Regression tests: --only/--exclude must accept the detector short names.

`--list-detectors` prints short names (`rust-cargo`) and the docs use them
(`--only rust-cargo,node`), but validation only accepted the internal keys
(`rust_drifts`). Copying any name out of `--list-detectors` therefore failed
with "unknown detector".
"""

import subprocess
import sys

import pytest

from driftcheck.cli import (
    DETECTOR_INFO,
    _detector_aliases,
    _resolve_detector_names,
    _validate_detector_names,
)


class TestDetectorAliases:
    def test_short_names_are_unique(self):
        shorts = [short for short, _ in DETECTOR_INFO.values()]
        assert len(shorts) == len(set(shorts)), "short names must be unique to map safely"

    def test_no_short_name_collides_with_a_key(self):
        overlap = {short for short, _ in DETECTOR_INFO.values()} & set(DETECTOR_INFO)
        assert not overlap, f"short name collides with internal key: {overlap}"

    def test_every_short_name_resolves_to_its_key(self):
        aliases = _detector_aliases()
        for key, (short, _desc) in DETECTOR_INFO.items():
            assert aliases[short] == key
            assert aliases[key] == key

    def test_unknown_names_still_rejected(self, capsys):
        assert _validate_detector_names({"not_a_detector"}, "--only") == [
            "not_a_detector"
        ]

    def test_resolve_mixes_short_and_key(self):
        resolved = _resolve_detector_names({"rust-cargo", "node_drifts", "bogus"})
        assert resolved == {"rust_drifts", "node_drifts"}


class TestCliShortNames:
    """End-to-end: the names printed by --list-detectors must work on input."""

    @pytest.fixture()
    def project(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test\n\nRust 1.75\n")
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "x"\nversion = "0.1.0"\n\n'
            '[package.metadata.driftcheck]\nrust-version = "1.75"\n'
        )
        return tmp_path

    def _run(self, args, project):
        return subprocess.run(
            [sys.executable, "-m", "driftcheck.cli", *args, str(project)],
            capture_output=True,
            text=True,
        )

    def test_only_accepts_short_name(self, project):
        result = self._run(["--only", "rust-cargo"], project)
        assert "unknown detector" not in result.stderr, result.stderr
        assert result.returncode != 2, result.stderr

    def test_only_accepts_comma_separated_short_names(self, project):
        result = self._run(["--only", "rust-cargo,node"], project)
        assert "unknown detector" not in result.stderr, result.stderr

    def test_only_still_accepts_internal_key(self, project):
        result = self._run(["--only", "rust_drifts"], project)
        assert "unknown detector" not in result.stderr, result.stderr

    def test_only_all_invalid_still_exits_two(self, project):
        result = self._run(["--only", "totally-bogus"], project)
        assert result.returncode == 2
        assert "no valid detector names" in result.stderr

    def test_exclude_accepts_short_name(self, project):
        result = self._run(["--exclude", "rust-cargo"], project)
        assert "unknown detector" not in result.stderr, result.stderr
