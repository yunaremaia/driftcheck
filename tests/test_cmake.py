"""Tests for CMake drift detection."""
from pathlib import Path

from driftcheck.detectors.cmake import (
    parse_cmake_version,
    find_cmake_drift,
    CMAKE_VERSION_RE,
    CMAKE_DOC_RE,
)


class TestParseCmakeVersion:
    def test_basic(self):
        assert parse_cmake_version("cmake_minimum_required(VERSION 3.16)") == "3.16"

    def test_with_decimal(self):
        assert parse_cmake_version("cmake_minimum_required(VERSION 3.20.5)") == "3.20.5"

    def test_uppercase(self):
        assert parse_cmake_version("CMAKE_MINIMUM_REQUIRED(VERSION 3.14)") == "3.14"

    def test_mixed_case(self):
        assert parse_cmake_version("CMake_Minimum_Required(VERSION 3.18)") == "3.18"

    def test_no_match(self):
        assert parse_cmake_version("some other content") is None


class TestFindCmakeDrift:
    def test_drift_detected(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        docs = {"README.md": "Requires CMake 3.16"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "3.16"
        assert result[0]["cmake_version"] == "3.20"

    def test_no_drift(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        docs = {"README.md": "Requires CMake 3.20"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 0

    def test_no_docs(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        result = find_cmake_drift(cmake, {})
        assert len(result) == 0

    def test_no_cmake_version(self):
        cmake = "some other content"
        docs = {"README.md": "Requires CMake 3.20"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 0

    def test_patch_difference_ignored(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        docs = {"README.md": "Requires CMake 3.20.5"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 0

    def test_multiple_files(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        docs = {
            "README.md": "Requires CMake 3.16",
            "CONTRIBUTING.md": "CMake 3.14 needed",
        }
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 2
