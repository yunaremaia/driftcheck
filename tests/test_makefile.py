"""Tests for Makefile drift detection."""
from pathlib import Path
from driftcheck.detectors.makefile import (
    parse_makefile_versions,
    find_makefile_drift,
    MAKEFILE_VERSION_VAR_RE,
    MAKEFILE_TOOL_ASSIGN_RE,
)


def test_parse_makefile_versions_version_vars():
    """Parse GCC_VERSION, CMAKE_VERSION style variables."""
    text = """
GCC_VERSION = 13.2.0
CMAKE_VERSION := 3.28.1
GO_VERSION ?= 1.22
"""
    result = parse_makefile_versions(text)
    assert "GCC_VERSION" in result
    assert result["GCC_VERSION"] == "13.2.0"
    assert "CMAKE_VERSION" in result
    assert result["CMAKE_VERSION"] == "3.28.1"
    assert "GO_VERSION" in result
    assert result["GO_VERSION"] == "1.22"


def test_parse_makefile_versions_tool_assign():
    """Parse tool assignments with version-style values."""
    text = """
GO = 1.22
NODE = 20.11
PYTHON = 3.12
CMAKE = cmake
"""
    result = parse_makefile_versions(text)
    assert "GO" in result
    assert result["GO"] == "1.22"
    assert "NODE" in result
    assert result["NODE"] == "20.11"
    assert "PYTHON" in result
    assert result["PYTHON"] == "3.12"
    # Non-version assignments are ignored
    assert "CMAKE" not in result


def test_parse_makefile_versions_mixed():
    """Parse mixed style assignments."""
    text = """
GCC_VERSION := 14.1.0
GO = 1.22
CMAKE_VERSION = 3.29.0
"""
    result = parse_makefile_versions(text)
    assert "GCC_VERSION" in result
    assert "GO" in result
    assert "CMAKE_VERSION" in result


def test_find_makefile_drift_match():
    """No drift when versions match."""
    makefile = "GCC_VERSION = 13.2.0\n"
    docs = {"README.md": "This project requires GCC 13.2"}
    result = find_makefile_drift(makefile, docs)
    assert result == []


def test_find_makefile_drift_mismatch():
    """Detect drift when Makefile and docs differ."""
    makefile = "GCC_VERSION = 14.1.0\n"
    docs = {"README.md": "This project requires GCC 13"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 1
    assert result[0]["doc_version"] == "13"
    assert result[0]["makefile_version"] == "14.1.0"
    assert result[0]["tool"] == "GCC"


def test_find_makefile_drift_cmake():
    """Detect drift for CMAKE_VERSION."""
    makefile = "CMAKE_VERSION := 3.29.0\n"
    docs = {"README.md": "Requires CMake 3.27"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 1
    assert result[0]["tool"] == "CMAKE"


def test_find_makefile_drift_multiple():
    """Detect multiple drifts in same docs."""
    makefile = "GCC_VERSION = 14.1.0\nGO_VERSION = 1.23\n"
    docs = {"README.md": "Requires GCC 13 and Go 1.22"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 2
    tools = {d["tool"] for d in result}
    assert "GCC" in tools
    assert "GO" in tools


def test_find_makefile_drift_ignores_non_version():
    """Ignore non-version assignments."""
    text = """
CC = gcc
CFLAGS = -Wall -O2
TARGET = app
"""
    result = parse_makefile_versions(text)
    assert "CFLAGS" not in result
    assert "TARGET" not in result


def test_find_makefile_drift_case_insensitive():
    """Match case-insensitively."""
    makefile = "GCC_VERSION = 14.1.0\n"
    docs = {"README.md": "Requires gcc 13"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 1


def test_makefile_version_var_re():
    """Regex matches Makefile version variable assignments."""
    text = "GCC_VERSION = 13.2.0"
    m = MAKEFILE_VERSION_VAR_RE.search(text)
    assert m is not None
    assert m.group("ver") == "13.2.0"


def test_makefile_tool_assign_re():
    """Regex matches Makefile tool assignments."""
    text = "CC = gcc-13"
    m = MAKEFILE_TOOL_ASSIGN_RE.search(text)
    assert m is not None
    assert m.group("ver") == "gcc-13"


def test_find_makefile_drift_no_makefile():
    """No drift if Makefile has no version info."""
    makefile = "all:\n\techo hello\n"
    docs = {"README.md": "Requires GCC 13"}
    result = find_makefile_drift(makefile, docs)
    assert result == []


def test_find_makefile_drift_empty_docs():
    """No drift if docs are empty."""
    makefile = "GCC_VERSION = 14.1.0\n"
    docs = {"README.md": ""}
    result = find_makefile_drift(makefile, docs)
    assert result == []


def test_find_makefile_drift_no_minor_diff():
    """No drift when only patch version differs."""
    makefile = "GCC_VERSION = 14.1.0\n"
    docs = {"README.md": "Requires GCC 14.1.2"}
    result = find_makefile_drift(makefile, docs)
    assert result == []


def test_find_makefile_drift_major_diff():
    """Drift detected when major version differs."""
    makefile = "GCC_VERSION = 14.1.0\n"
    docs = {"README.md": "Requires GCC 13.2"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 1


def test_find_makefile_drift_contributing():
    """Detect drift in CONTRIBUTING.md too."""
    makefile = "CMAKE_VERSION := 3.29.0\n"
    docs = {"CONTRIBUTING.md": "Build with CMake 3.27"}
    result = find_makefile_drift(makefile, docs)
    assert len(result) == 1
    assert result[0]["file"] == "CONTRIBUTING.md"


def test_makefile_re_match_cc():
    """CC assignment regex captures version."""
    text = "CC = gcc-13.2.0"
    m = MAKEFILE_TOOL_ASSIGN_RE.search(text)
    assert m is not None
    assert m.group("ver") == "gcc-13.2.0"


def test_makefile_re_match_conditional():
    """Conditional assignment ?= is captured."""
    text = "GO_VERSION ?= 1.22"
    m = MAKEFILE_VERSION_VAR_RE.search(text)
    assert m is not None
    assert m.group("ver") == "1.22"
