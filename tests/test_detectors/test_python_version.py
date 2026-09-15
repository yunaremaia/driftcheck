"""Tests for python_version detector: .python-version vs requires-python floor."""
import pytest
from driftcheck.detectors.python_version import (
    parse_python_version_file,
    parse_requires_python,
    find_python_version_file_drift,
    _normalize_version,
)


class TestNormalizeVersion:
    def test_major_minor(self):
        assert _normalize_version("3.12") == (3, 12, 0)

    def test_major_minor_patch(self):
        assert _normalize_version("3.12.5") == (3, 12, 5)

    def test_prerelease(self):
        assert _normalize_version("3.13.0rc1") == (3, 13, 0)

    def test_invalid(self):
        assert _normalize_version("not-a-version") == (0, 0, 0)


class TestParsePythonVersionFile:
    def test_simple_version(self):
        assert parse_python_version_file("3.12.5") == (3, 12, 5)

    def test_with_comment(self):
        assert parse_python_version_file("3.12.5  # production") == (3, 12, 5)

    def test_with_hash_comment_line(self):
        assert parse_python_version_file("# production\n3.12.5") == (3, 12, 5)

    def test_major_only(self):
        assert parse_python_version_file("3") == (3, 0, 0)

    def test_prerelease(self):
        assert parse_python_version_file("3.13.0rc1") == (3, 13, 0)

    def test_empty(self):
        assert parse_python_version_file("") is None

    def test_only_comments(self):
        assert parse_python_version_file("# comment\n# another") is None

    def test_with_whitespace(self):
        assert parse_python_version_file("  3.12.5  ") == (3, 12, 5)


class TestParseRequiresPython:
    def test_floor(self):
        assert parse_requires_python('requires-python = ">=3.10"') == (3, 10, 0)

    def test_range(self):
        assert parse_requires_python('requires-python = ">=3.10,<3.13"') == (3, 10, 0)

    def test_compatible(self):
        assert parse_requires_python('requires-python = "~=3.11"') == (3, 11, 0)

    def test_setup_cfg(self):
        assert parse_requires_python("python_requires = >=3.8") == (3, 8, 0)

    def test_missing(self):
        assert parse_requires_python("[project]\nname = 'foo'") is None


class TestFindPythonVersionFileDrift:
    def test_no_drift_pin_above_floor(self):
        result = find_python_version_file_drift("3.12", 'requires-python = ">=3.10"')
        assert result == []

    def test_no_drift_pin_equals_floor(self):
        result = find_python_version_file_drift("3.10", 'requires-python = ">=3.10"')
        assert result == []

    def test_drift_pin_below_floor(self):
        result = find_python_version_file_drift("3.9", 'requires-python = ">=3.10"')
        assert len(result) == 1
        assert result[0]["pin_version"] == "3.9.0"
        assert result[0]["floor_version"] == "3.10.0"
        assert result[0]["floor_source"] == "pyproject.toml"

    def test_missing_python_version(self):
        result = find_python_version_file_drift(None, 'requires-python = ">=3.10"')
        assert result == []

    def test_missing_requires_python(self):
        result = find_python_version_file_drift("3.12", None)
        assert result == []

    def test_setup_cfg_fallback(self):
        result = find_python_version_file_drift("3.7", None, "python_requires = >=3.8")
        assert len(result) == 1
        assert result[0]["floor_source"] == "setup.cfg"

    def test_pyproject_takes_precedence_over_setup_cfg(self):
        result = find_python_version_file_drift(
            "3.7", 'requires-python = ">=3.8"', 'python_requires = ">=3.9"'
        )
        assert len(result) == 1
        assert result[0]["floor_source"] == "pyproject.toml"
        assert result[0]["floor_version"] == "3.8.0"

    def test_unparseable_pin(self):
        result = find_python_version_file_drift("not-a-version", 'requires-python = ">=3.10"')
        assert result == []
