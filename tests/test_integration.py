"""Integration tests for driftcheck CLI — end-to-end with real temp directories."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from driftcheck.cli import main


def run_cli(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run driftcheck CLI, return (rc, stdout, stderr)."""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    rc = 1
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        try:
            rc = main(args)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, stdout_buf.getvalue(), stderr_buf.getvalue()


def make_gitattributes(path: Path):
    """Create a .gitattributes that passes lineending check."""
    (path / ".gitattributes").write_text(
        "# Normalize line endings\n* text=auto eol=lf\n"
    )


class TestCLINoDrift:
    """CLI returns 0 and OK message when no drift detected."""

    def test_no_toolchain(self, tmp_path):
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "no toolchain version found" in out

    def test_rust_no_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.96.1")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out
        assert "Rust 1.96.1" in out

    def test_node_no_drift(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "24.x"}}')
        (tmp_path / "README.md").write_text("Install Node.js 24")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out
        assert "Node 24" in out

    def test_python_no_drift(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10"')
        (tmp_path / "README.md").write_text("Python 3.10+")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out
        assert "Python 3.10" in out

    def test_go_no_drift(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/foo\ngo 1.23")
        (tmp_path / "README.md").write_text("Build with Go 1.23")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out
        assert "Go 1.23" in out


class TestCLIDetectsDrift:
    """CLI returns 1 and prints drift details when drift exists."""

    def test_rust_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.93.0")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Rust 1.93.0" in out
        assert "should be 1.96.1" in out

    def test_node_drift(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "24.x"}}')
        (tmp_path / "README.md").write_text("Install Node.js 18")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Node 18" in out
        assert "should be 24" in out

    def test_python_drift(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"')
        (tmp_path / "README.md").write_text("Python 3.10+")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Python 3.10" in out
        assert "should be 3.12" in out

    def test_go_drift(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/foo\ngo 1.23")
        (tmp_path / "README.md").write_text("Build with Go 1.21")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Go 1.21" in out
        assert "should be 1.23" in out


class TestCLIJsonOutput:
    """CLI --json returns valid JSON with expected structure."""

    def test_json_no_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.96.1")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        assert rc == 0
        data = json.loads(out)
        assert data["toolchain_version"] == "1.96.1"
        assert data["drifts"] == []

    def test_json_with_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.93.0")
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        assert rc == 1
        data = json.loads(out)
        assert data["toolchain_version"] == "1.96.1"
        assert len(data["drifts"]) == 1
        assert data["drifts"][0]["doc_version"] == "1.93.0"

    def test_json_multiple_detectors(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "package.json").write_text('{"engines": {"node": "24.x"}}')
        (tmp_path / "README.md").write_text("Rust 1.93.0 and Node 18")
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        assert rc == 1
        data = json.loads(out)
        assert data["toolchain_version"] == "1.96.1"
        assert data["package_node"] == "24"


class TestCLIFix:
    """CLI --fix auto-corrects drift in docs."""

    def test_fix_rust_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.93.0")
        rc, out, _ = run_cli([str(tmp_path), "--fix"])
        assert rc == 0
        assert "fixed" in out
        content = (tmp_path / "README.md").read_text()
        assert "1.96.1" in content
        assert "1.93.0" not in content

    def test_fix_node_drift(self, tmp_path):
        (tmp_path / "package.json").write_text('{"engines": {"node": "24.x"}}')
        (tmp_path / "README.md").write_text("Install Node.js 18")
        rc, out, _ = run_cli([str(tmp_path), "--fix"])
        assert rc == 0
        assert "fixed" in out
        content = (tmp_path / "README.md").read_text()
        assert "24" in content
        assert "18" not in content

    def test_fix_no_drift(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Install Rust 1.96.1")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--fix"])
        assert rc == 0
        assert "no drifts to fix" in out


class TestCLIMultiFile:
    """CLI handles multiple doc files (README, CONTRIBUTING, docs/README.*)."""

    def test_drift_in_contributing(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Rust 1.96.1")
        (tmp_path / "CONTRIBUTING.md").write_text("Build with Rust 1.90.0")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "CONTRIBUTING.md" in out

    def test_drift_in_docs_subdir(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Rust 1.96.1")
        (docs / "README.zh-CN.md").write_text("Rust 1.90.0")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "docs" in out and "README.zh-CN.md" in out


class TestCLILineEnding:
    """CLI detects missing .gitattributes."""

    def test_missing_gitattributes(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Rust 1.96.1")
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert any(d["kind"] == "lineending" for d in data.get("lineending_drifts", []))

    def test_fix_gitattributes(self, tmp_path):
        (tmp_path / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (tmp_path / "README.md").write_text("Rust 1.96.1")
        rc, out, _ = run_cli([str(tmp_path), "--fix"])
        assert rc == 0
        ga = tmp_path / ".gitattributes"
        assert ga.exists()
        content = ga.read_text()
        assert "text=auto eol=lf" in content


class TestCLIRuby:
    """CLI detects Ruby version drift."""

    def test_ruby_no_drift(self, tmp_path):
        (tmp_path / "Gemfile").write_text('ruby "3.2.2"')
        (tmp_path / "README.md").write_text("Ruby 3.2")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out

    def test_ruby_detects_drift(self, tmp_path):
        (tmp_path / "Gemfile").write_text('ruby "3.2.2"')
        (tmp_path / "README.md").write_text("Ruby 3.0")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Ruby 3.0" in out
        assert "should be 3.2" in out


class TestCLIDotnet:
    """CLI detects .NET version drift."""

    def test_dotnet_no_drift(self, tmp_path):
        (tmp_path / "MyApp.csproj").write_text('<TargetFramework>net8.0</TargetFramework>')
        (tmp_path / "README.md").write_text("Targets .NET 8.0")
        make_gitattributes(tmp_path)
        # Create dependabot.yml to avoid dependabot drift
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            "version: 2\nupdates:\n  - package-ecosystem: \"nuget\"\n    directory: \"/\"\n    schedule:\n      interval: \"weekly\"\n"
        )
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 0
        assert "OK" in out

    def test_dotnet_detects_drift(self, tmp_path):
        (tmp_path / "MyApp.csproj").write_text('<TargetFramework>net8.0</TargetFramework>')
        (tmp_path / "README.md").write_text("Targets .NET 7.0")
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert ".NET 7.0" in out
        assert "should be 8.0" in out
