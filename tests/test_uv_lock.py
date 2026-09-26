"""Tests for uv.lock content drift detection."""

from __future__ import annotations
import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.uv_lock import (
    parse_uv_lock,
    parse_pyproject_uv_deps,
    find_uv_lock_drift,
)


class TestParseUvLock:
    def test_single_package(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1

[[package]]
name = "requests"
version = "2.32.0"
source = { index = "pypi" }
""")
        result = parse_uv_lock(str(uv_lock))
        assert result == {"requests": "2.32.0"}

    def test_multiple_packages(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1

[[package]]
name = "requests"
version = "2.32.0"
source = { index = "pypi" }

[[package]]
name = "flask"
version = "3.0.0"
source = { index = "pypi" }
""")
        result = parse_uv_lock(str(uv_lock))
        assert result == {"requests": "2.32.0", "flask": "3.0.0"}

    def test_empty_file(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("")
        result = parse_uv_lock(str(uv_lock))
        assert result == {}

    def test_missing_file(self, tmp_path):
        result = parse_uv_lock(str(tmp_path / "nonexistent.lock"))
        assert result == {}

    def test_transitive_deps(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1

[[package]]
name = "requests"
version = "2.32.0"
source = { index = "pypi" }

[[package]]
name = "urllib3"
version = "2.0.7"
source = { index = "pypi" }

[[package]]
name = "certifi"
version = "2023.11.17"
source = { index = "pypi" }
""")
        result = parse_uv_lock(str(uv_lock))
        assert result == {
            "requests": "2.32.0",
            "urllib3": "2.0.7",
            "certifi": "2023.11.17",
        }


class TestParsePyprojectUvDeps:
    def test_single_dependency(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = [
    "requests>=2.28.0",
    "flask>=3.0.0",
]
""")
        result = parse_pyproject_uv_deps(pyproject.read_text())
        assert result == {"requests": ">=2.28.0", "flask": ">=3.0.0"}

    def test_no_dependencies(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = \"test\"\nversion = \"0.1.0\"")
        result = parse_pyproject_uv_deps(pyproject.read_text())
        assert result == {}

    def test_empty_file(self, tmp_path):
        result = parse_pyproject_uv_deps("")
        assert result == {}

    def test_skips_python(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = [
    "python>=3.10",
    "requests>=2.28.0",
]
""")
        result = parse_pyproject_uv_deps(pyproject.read_text())
        assert "python" not in result
        assert result == {"requests": ">=2.28.0"}


class TestFindUvLockDrift:
    def test_no_uv_lock(self, tmp_path):
        result = find_uv_lock_drift(str(tmp_path))
        assert result == []

    def test_uv_lock_without_pyproject(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1
[[package]]
name = "requests"
version = "2.32.0"
""")
        result = find_uv_lock_drift(str(tmp_path))
        assert result == []

    def test_matching_versions(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1
[[package]]
name = "requests"
version = "2.32.0"
""")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]
""")
        result = find_uv_lock_drift(str(tmp_path))
        assert len(result) == 1
        assert result[0]["package"] == "requests"
        assert result[0]["uv_lock_version"] == "2.32.0"
        assert result[0]["pyproject_spec"] == ">=2.28.0"

    def test_multiple_packages(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("""
version = 1
[[package]]
name = "requests"
version = "2.32.0"
[[package]]
name = "flask"
version = "3.0.0"
""")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0", "flask>=3.0.0"]
""")
        result = find_uv_lock_drift(str(tmp_path))
        assert len(result) == 2

    def test_malformed_toml(self, tmp_path):
        uv_lock = tmp_path / "uv.lock"
        uv_lock.write_text("this is not valid toml {{{")
        result = find_uv_lock_drift(str(tmp_path))
        assert result == []
