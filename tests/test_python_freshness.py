"""Tests for python_freshness detector."""
from __future__ import annotations
import pytest

from driftcheck.detectors.python_freshness import (
    parse_pinned_requirements,
    parse_pinned_pyproject,
    find_python_dep_freshness,
)


class TestParsePinnedRequirements:
    def test_simple_pin(self):
        text = "requests==2.28.0\nflask==2.0.1\n"
        result = parse_pinned_requirements(text)
        assert result == {"requests": "2.28.0", "flask": "2.0.1"}

    def test_comments_and_blank_lines(self):
        text = "# dependencies\nrequests==2.28.0  # HTTP library\n\nflask==2.0.1\n"
        result = parse_pinned_requirements(text)
        assert result == {"requests": "2.28.0", "flask": "2.0.1"}

    def test_non_pinned_skipped(self):
        text = "requests>=2.28.0\nflask~=2.0.1\n"
        result = parse_pinned_requirements(text)
        assert result == {}

    def test_known_packages_skipped(self):
        text = "pip==23.0\nsetuptools==65.0\nwheel==0.38.0\npython==3.10\npackaging==21.0\n"
        result = parse_pinned_requirements(text)
        assert result == {}

    def test_package_with_dots_and_dashes(self):
        text = "azure-storage-blob==12.14.0\ngoogle-cloud-storage==2.10.0\n"
        result = parse_pinned_requirements(text)
        assert "azure-storage-blob" in result
        assert "google-cloud-storage" in result

    def test_underscore_normalized_to_dash(self):
        text = "python_request_sdk==1.0.0\n"
        result = parse_pinned_requirements(text)
        assert "python-request-sdk" in result


class TestParsePinnedPyproject:
    def test_project_dependencies(self):
        text = '''
[project]
dependencies = [
    "requests==2.28.0",
    "flask==2.0.1",
]
'''
        result = parse_pinned_pyproject(text)
        assert result == {"requests": "2.28.0", "flask": "2.0.1"}

    def test_poetry_dependencies(self):
        text = '''
[tool.poetry.dependencies]
python = "^3.9"
requests = "==2.28.0"
flask = "^2.0.0"
'''
        result = parse_pinned_pyproject(text)
        assert result["requests"] == "2.28.0"
        # flask with caret: minimum version extracted
        assert result["flask"] == "2.0.0"

    def test_mixed_constraints(self):
        text = '''
[project]
dependencies = [
    "requests==2.28.0",
    "flask>=2.0.0",
    "click~=8.0",
]
'''
        result = parse_pinned_pyproject(text)
        assert result["requests"] == "2.28.0"
        assert result["flask"] == "2.0.0"
        assert result["click"] == "8.0"

    def test_python_requirement_skipped(self):
        text = '''
[project]
dependencies = [
    "python>=3.8",
    "requests==2.28.0",
]
'''
        result = parse_pinned_pyproject(text)
        assert "python" not in result
        assert "requests" in result


class TestFindPythonDepFreshness:
    def test_no_pinned_packages(self):
        result = find_python_dep_freshness("", "")
        assert result == []

    def test_offline_mode_returns_empty(self):
        result = find_python_dep_freshness("requests==2.28.0\n", "", offline=True)
        assert result == []

    def test_cache_mode(self):
        result = find_python_dep_freshness(
            "requests==2.28.0\n",
            "",
            cache={"requests": "2.31.0"},
        )
        assert len(result) == 1
        assert result[0]["package"] == "requests"
        assert result[0]["pinned_version"] == "2.28.0"
        assert result[0]["latest_version"] == "2.31.0"
        assert result[0]["file"] == "requirements.txt"

    def test_up_to_date_package_not_reported(self):
        result = find_python_dep_freshness(
            "requests==2.31.0\n",
            "",
            cache={"requests": "2.31.0"},
        )
        assert result == []

    def test_multiple_packages_mixed_freshness(self):
        result = find_python_dep_freshness(
            "requests==2.28.0\nflask==2.3.0\n",
            "",
            cache={"requests": "2.31.0", "flask": "2.3.0"},
        )
        assert len(result) == 1
        assert result[0]["package"] == "requests"

    def test_pyproject_source_file(self):
        result = find_python_dep_freshness(
            "",
            '''[project]
dependencies = ["requests==2.28.0"]
''',
            cache={"requests": "2.31.0"},
        )
        assert len(result) == 1
        assert result[0]["file"] == "pyproject.toml"
        assert result[0]["package"] == "requests"

    def test_invalid_version_skipped(self):
        result = find_python_dep_freshness(
            "requests==abc\n",
            "",
            cache={"requests": "2.31.0"},
        )
        assert result == []

    def test_dev_release_not_considered_later(self):
        """Dev releases (e.g. 2.31.0rc1) should not beat a stable release."""
        result = find_python_dep_freshness(
            "requests==2.31.0\n",
            "",
            cache={"requests": "2.31.0rc1"},
        )
        assert result == []
