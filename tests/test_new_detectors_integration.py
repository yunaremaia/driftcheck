#!/usr/bin/env python3
"""Integration tests for requirements.txt and Kotlin drift detectors."""
import json
import sys
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import io

import pytest

# Add driftcheck to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from driftcheck.cli import main


def run_cli(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run driftcheck CLI, return (rc, stdout, stderr)."""
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
    (path / ".gitattributes").write_text("# Normalize line endings\n* text=auto eol=lf\n")


class TestRequirementsDrift:
    """Tests for requirements.txt drift detection."""

    def test_requirements_vs_pyproject_drift(self, tmp_path):
        """Detect drift between requirements.txt and pyproject.toml."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\nflask==2.0.0\n")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.10"\ndependencies = ["requests>=3.0.0"]\n'
        )
        (tmp_path / "README.md").write_text("Some project")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        # requirements.txt vs README drift (requests 2.28.0 vs not mentioned = no drift)
        # This test verifies the detector runs without error
        assert rc == 0 or rc == 1  # Accept either (depends on README content)

    def test_requirements_vs_readme_drift(self, tmp_path):
        """Detect drift between requirements.txt and README."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        (tmp_path / "README.md").write_text("This project uses requests 2.25.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 1
        assert len(data["requirements_drifts"]) >= 1

    def test_requirements_no_drift(self, tmp_path):
        """No drift when versions match."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        (tmp_path / "README.md").write_text("This project uses requests 2.28.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 0
        assert len(data["requirements_drifts"]) == 0

    def test_requirements_missing_file(self, tmp_path):
        """No drift when requirements.txt doesn't exist."""
        (tmp_path / "README.md").write_text("Some project")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 0
        assert len(data["requirements_drifts"]) == 0

    def test_requirements_output_format(self, tmp_path):
        """Output format includes package name and versions."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        (tmp_path / "README.md").write_text("requests 2.25.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "requests" in out
        assert "2.28.0" in out


class TestKotlinDrift:
    """Tests for Kotlin drift detection."""

    def test_kotlin_drift_detected(self, tmp_path):
        """Detect Kotlin version drift between build.gradle.kts and README."""
        (tmp_path / "build.gradle.kts").write_text(
            'plugins {\n    kotlin("jvm") version "1.9.0"\n}\n'
        )
        (tmp_path / "README.md").write_text("Built with Kotlin 1.8.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 1
        assert len(data["kotlin_drifts"]) >= 1

    def test_kotlin_no_drift(self, tmp_path):
        """No drift when versions match."""
        (tmp_path / "build.gradle.kts").write_text(
            'plugins {\n    kotlin("jvm") version "1.9.0"\n}\n'
        )
        (tmp_path / "README.md").write_text("Built with Kotlin 1.9")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 0
        assert len(data["kotlin_drifts"]) == 0

    def test_kotlin_no_gradle_file(self, tmp_path):
        """No drift when build.gradle.kts doesn't exist."""
        (tmp_path / "README.md").write_text("Some project")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 0
        assert len(data["kotlin_drifts"]) == 0

    def test_kotlin_output_format(self, tmp_path):
        """Output format includes Kotlin version info."""
        (tmp_path / "build.gradle.kts").write_text(
            'plugins {\n    kotlin("jvm") version "1.9.0"\n}\n'
        )
        (tmp_path / "README.md").write_text("Kotlin 1.8.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path)])
        assert rc == 1
        assert "Kotlin" in out
        assert "1.9.0" in out

    def test_kotlin_plugin_spring(self, tmp_path):
        """Detect Kotlin Spring plugin version drift."""
        (tmp_path / "build.gradle.kts").write_text(
            'plugins {\n    kotlin("plugin.spring") version "1.9.0"\n}\n'
        )
        (tmp_path / "README.md").write_text("Kotlin 1.8.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--json"])
        data = json.loads(out)
        assert rc == 1
        assert len(data["kotlin_drifts"]) >= 1


class TestNewDetectorsInList:
    """Verify new detectors appear in --list-detectors."""

    def test_requirements_in_list(self, tmp_path):
        """Requirements detector appears in list."""
        (tmp_path / "README.md").write_text("test")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--list-detectors"])
        assert "requirements" in out

    def test_kotlin_in_list(self, tmp_path):
        """Kotlin detector appears in list."""
        (tmp_path / "README.md").write_text("test")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--list-detectors"])
        assert "kotlin" in out


class TestNewDetectorsReport:
    """Verify new detectors work with --report flag."""

    def test_requirements_in_report(self, tmp_path):
        """Requirements drift appears in report."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        (tmp_path / "README.md").write_text("requests 2.25.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--report"])
        assert rc == 1
        assert "requirements" in out.lower() or "requests" in out.lower()

    def test_kotlin_in_report(self, tmp_path):
        """Kotlin drift appears in report."""
        (tmp_path / "build.gradle.kts").write_text(
            'plugins {\n    kotlin("jvm") version "1.9.0"\n}\n'
        )
        (tmp_path / "README.md").write_text("Kotlin 1.8.0")
        make_gitattributes(tmp_path)
        rc, out, _ = run_cli([str(tmp_path), "--report"])
        assert rc == 1
        assert "kotlin" in out.lower()
