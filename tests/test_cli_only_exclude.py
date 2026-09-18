"""Tests for --only/--exclude detector name validation."""

import pytest
from driftcheck.cli import _validate_detector_names, DETECTOR_INFO


class TestValidateDetectorNames:
    """_validate_detector_names returns unknown names and prints suggestions."""

    def test_all_valid_returns_empty(self, capsys):
        names = {"rust_drifts", "node_drifts", "python_drifts"}
        unknown = _validate_detector_names(names, "test")
        assert unknown == []
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_all_invalid_returns_all(self, capsys):
        names = {"foo_bar", "baz_qux"}
        unknown = _validate_detector_names(names, "test")
        assert set(unknown) == names
        captured = capsys.readouterr()
        assert "foo_bar" in captured.err
        assert "baz_qux" in captured.err

    def test_mixed_returns_only_invalid(self, capsys):
        names = {"rust_drifts", "foo_bar"}
        unknown = _validate_detector_names(names, "test")
        assert unknown == ["foo_bar"]
        captured = capsys.readouterr()
        assert "foo_bar" in captured.err
        assert "rust_drifts" not in captured.err

    def test_empty_set_returns_empty(self):
        unknown = _validate_detector_names(set(), "test")
        assert unknown == []

    def test_case_sensitive(self):
        """Detector names are case-sensitive (RUST_DRIFTS != rust_drifts)."""
        unknown = _validate_detector_names({"RUST_DRIFTS"}, "test")
        assert unknown == ["RUST_DRIFTS"]

    def test_fuzzy_suggestion(self, capsys):
        """Typo in name produces close-match suggestion."""
        _validate_detector_names({"rust_drfit"}, "--only")
        captured = capsys.readouterr()
        assert "rust_drifts" in captured.err
        assert "did you mean" in captured.err

    def test_all_known_detectors_valid(self):
        """Every key in DETECTOR_INFO passes validation."""
        unknown = _validate_detector_names(set(DETECTOR_INFO.keys()), "test")
        assert unknown == []


class TestCliOnlyExcludeValidation:
    """Integration tests for --only/--exclude validation via CLI."""

    def test_only_valid_detector(self, tmp_path, capsys):
        """--only with valid detector name works normally."""
        (tmp_path / "README.md").write_text("# Test\n\nPython 3.9\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nrequires-python = \">=3.10\"\n")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "driftcheck.cli", "--only", "python_drifts", str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 1  # drift detected (3.9 vs 3.10)

    def test_only_typo_exits_nonzero(self, tmp_path):
        """--only with typo exits with code 2 and prints suggestion."""
        (tmp_path / "README.md").write_text("# Test\n")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "driftcheck.cli", "--only", "rust_drfit", str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 2
        assert "rust_drifts" in result.stderr

    def test_exclude_typo_warns_but_continues(self, tmp_path):
        """--exclude with typo warns but still runs other detectors."""
        (tmp_path / "README.md").write_text("# Test\n\nPython 3.9\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nrequires-python = \">=3.10\"\n")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "driftcheck.cli", "--exclude", "python_drfit", str(tmp_path)],
            capture_output=True, text=True
        )
        # python_drfit is excluded from exclusion list, so python detector runs
        assert result.returncode == 1  # drift still detected
        assert "python_drifts" in result.stderr

    def test_only_mixed_valid_invalid(self, tmp_path):
        """--only with one valid and one invalid name: warns but still runs valid."""
        (tmp_path / "README.md").write_text("# Test\n\nPython 3.9\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nrequires-python = \">=3.10\"\n")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "driftcheck.cli", "--only", "python_drifts,foo_bar", str(tmp_path)],
            capture_output=True, text=True
        )
        # foo_bar is filtered out (warning), python_drifts runs
        assert result.returncode == 1
        assert "foo_bar" in result.stderr
