"""Integration tests for new detectors."""
from pathlib import Path
import tempfile
import os

from driftcheck.detector import scan_repo


def _make_repo(tmp_path: Path, files: dict[str, str]):
    """Helper: write files into tmp_path."""
    for name, content in files.items():
        full = tmp_path / name
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")


class TestToolVersionsIntegration:
    def test_tool_versions_drift(self, tmp_path):
        _make_repo(tmp_path, {
            ".tool-versions": "node 20.12.0\npython 3.12.0\n",
            "README.md": "Uses Node 18 and Python 3.11",
        })
        result = scan_repo(tmp_path)
        assert len(result["tool_versions_drifts"]) == 2

    def test_tool_versions_no_drift(self, tmp_path):
        _make_repo(tmp_path, {
            ".tool-versions": "node 20.12.0\n",
            "README.md": "Uses Node 20.12.0",
        })
        result = scan_repo(tmp_path)
        assert len(result["tool_versions_drifts"]) == 0

    def test_tool_versions_missing(self, tmp_path):
        _make_repo(tmp_path, {
            "README.md": "Uses Node 18",
        })
        result = scan_repo(tmp_path)
        assert len(result["tool_versions_drifts"]) == 0


class TestNvmrcIntegration:
    def test_nvmrc_drift_vs_package(self, tmp_path):
        _make_repo(tmp_path, {
            ".nvmrc": "18.0.0\n",
            "package.json": '{"engines": {"node": ">=20.12.0"}}',
            "README.md": "",
        })
        result = scan_repo(tmp_path)
        assert len(result["nvmrc_drifts"]) == 1
        assert result["nvmrc_drifts"][0]["nvmrc_version"] == "18.0.0"

    def test_nvmrc_drift_vs_docs(self, tmp_path):
        _make_repo(tmp_path, {
            ".nvmrc": "20.12.0\n",
            "README.md": "This project requires Node.js 18",
        })
        result = scan_repo(tmp_path)
        assert len(result["nvmrc_drifts"]) == 1

    def test_nvmrc_no_drift(self, tmp_path):
        _make_repo(tmp_path, {
            ".nvmrc": "20.12.0\n",
            "package.json": '{"engines": {"node": ">=20.12.0"}}',
            "README.md": "Node 20.12",
        })
        result = scan_repo(tmp_path)
        assert len(result["nvmrc_drifts"]) == 0

    def test_nvmrc_missing(self, tmp_path):
        _make_repo(tmp_path, {
            "README.md": "Node 20",
        })
        result = scan_repo(tmp_path)
        assert len(result["nvmrc_drifts"]) == 0


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

