"""Tests for Elixir and CMake detectors."""
from pathlib import Path
import tempfile

from driftcheck.detectors.elixir import (
    parse_mix_elixir_version,
    find_elixir_drift,
    MIX_ELIXIR_RE,
)
from driftcheck.detectors.cmake import (
    parse_cmake_version,
    find_cmake_drift,
    CMAKE_VERSION_RE,
)


class TestParseMixElixirVersion:
    def test_standard(self):
        assert parse_mix_elixir_version('elixir: "~> 1.15"') == "1.15"

    def test_with_patch(self):
        assert parse_mix_elixir_version('elixir: "~> 1.15.4"') == "1.15.4"

    def test_no_space(self):
        assert parse_mix_elixir_version('elixir: "~>1.14"') == "1.14"

    def test_empty(self):
        assert parse_mix_elixir_version("") is None

    def test_no_elixir_key(self):
        assert parse_mix_elixir_version("some other content") is None


class TestFindElixirDrift:
    def test_no_drift(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "This project uses Elixir 1.15"}
        assert find_elixir_drift(mix, docs) == []

    def test_drift_major(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "This project uses Elixir 1.14"}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "1.14"
        assert result[0]["mix_version"] == "1.15"

    def test_drift_minor(self):
        mix = 'elixir: "~> 1.16"'
        docs = {"README.md": "Requires Elixir 1.15"}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 1

    def test_patch_ignored(self):
        mix = 'elixir: "~> 1.15.4"'
        docs = {"README.md": "Elixir 1.15.7"}
        assert find_elixir_drift(mix, docs) == []

    def test_empty_mix(self):
        assert find_elixir_drift("", {"README.md": "Elixir 1.15"}) == []

    def test_no_elixir_in_docs(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "A great project"}
        assert find_elixir_drift(mix, docs) == []


class TestParseCmakeVersion:
    def test_standard(self):
        assert parse_cmake_version("cmake_minimum_required(VERSION 3.16)") == "3.16"

    def test_with_patch(self):
        assert parse_cmake_version("cmake_minimum_required(VERSION 3.16.3)") == "3.16.3"

    def test_case_insensitive(self):
        assert parse_cmake_version("CMAKE_MINIMUM_REQUIRED(VERSION 3.20)") == "3.20"

    def test_empty(self):
        assert parse_cmake_version("") is None

    def test_no_cmake(self):
        assert parse_cmake_version("project(MyProject)") is None


class TestFindCmakeDrift:
    def test_no_drift(self):
        cmake = "cmake_minimum_required(VERSION 3.16)"
        docs = {"README.md": "Requires CMake 3.16"}
        assert find_cmake_drift(cmake, docs) == []

    def test_drift_major(self):
        cmake = "cmake_minimum_required(VERSION 3.20)"
        docs = {"README.md": "CMake 3.16 required"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "3.16"
        assert result[0]["cmake_version"] == "3.20"

    def test_drift_minor(self):
        cmake = "cmake_minimum_required(VERSION 3.18)"
        docs = {"README.md": "CMake 3.16"}
        result = find_cmake_drift(cmake, docs)
        assert len(result) == 1

    def test_patch_ignored(self):
        cmake = "cmake_minimum_required(VERSION 3.16.3)"
        docs = {"README.md": "CMake 3.16.7"}
        assert find_cmake_drift(cmake, docs) == []

    def test_empty_cmake(self):
        assert find_cmake_drift("", {"README.md": "CMake 3.16"}) == []

    def test_no_cmake_in_docs(self):
        cmake = "cmake_minimum_required(VERSION 3.16)"
        docs = {"README.md": "A great project"}
        assert find_cmake_drift(cmake, docs) == []


class TestIntegration:
    """Integration tests via scan_repo."""

    def test_elixir_drift_via_scan(self, tmp_path):
        from driftcheck.detector import scan_repo
        (tmp_path / "mix.exs").write_text('elixir: "~> 1.15"')
        (tmp_path / "README.md").write_text("This project uses Elixir 1.14")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = scan_repo(tmp_path)
        assert len(result["elixir_drifts"]) == 1

    def test_cmake_drift_via_scan(self, tmp_path):
        from driftcheck.detector import scan_repo
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)")
        (tmp_path / "README.md").write_text("Requires CMake 3.16")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = scan_repo(tmp_path)
        assert len(result["cmake_drifts"]) == 1

    def test_elixir_no_drift_via_scan(self, tmp_path):
        from driftcheck.detector import scan_repo
        (tmp_path / "mix.exs").write_text('elixir: "~> 1.15"')
        (tmp_path / "README.md").write_text("This project uses Elixir 1.15")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = scan_repo(tmp_path)
        assert len(result["elixir_drifts"]) == 0

    def test_cmake_no_drift_via_scan(self, tmp_path):
        from driftcheck.detector import scan_repo
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)")
        (tmp_path / "README.md").write_text("CMake 3.20")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = scan_repo(tmp_path)
        assert len(result["cmake_drifts"]) == 0
