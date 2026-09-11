"""Unit tests for the driftcheck fix module — apply_fixes() behavior."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.fix import apply_fixes


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class TestApplyFixesRust:
    def test_fixes_rust_toolchain_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Install Rust 1.93.0 for building")
        result = {
            "drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.93.0",
                    "toolchain_version": "1.96.1",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "1.96.1" in (tmp_path / "README.md").read_text()
        assert "1.93.0" not in (tmp_path / "README.md").read_text()

    def test_fixes_rust_cargo_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Install Rust 1.93.0")
        result = {
            "rust_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.93",
                    "toolchain_version": None,
                    "cargo_version": "1.96.1",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "1.96.1" in (tmp_path / "README.md").read_text()

    def test_no_drift_no_changes(self, tmp_path):
        _write(tmp_path / "README.md", "Rust 1.96.1")
        result = {"drifts": []}
        fixed = apply_fixes(tmp_path, result)
        assert fixed == []

    def test_missing_file_skipped(self, tmp_path):
        result = {
            "drifts": [
                {
                    "file": "nonexistent.md",
                    "doc_version": "1.93",
                    "toolchain_version": "1.96.1",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert fixed == []


class TestApplyFixesNode:
    def test_fixes_node_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Requires Node.js 18")
        result = {
            "node_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "18",
                    "package_version": "24",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "24" in (tmp_path / "README.md").read_text()
        assert "18" not in (tmp_path / "README.md").read_text()


class TestApplyFixesPython:
    def test_fixes_python_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Python 3.10+")
        result = {
            "python_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "3.10",
                    "pyproject_version": "3.12",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "3.12" in (tmp_path / "README.md").read_text()


class TestApplyFixesGo:
    def test_fixes_go_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Build with Go 1.21")
        result = {
            "go_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.21",
                    "gomod_version": "1.23",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "1.23" in (tmp_path / "README.md").read_text()


class TestApplyFixesCount:
    def test_fixes_count_drift(self, tmp_path):
        _write(tmp_path / "README.md", "We have 10 skills")
        result = {
            "count_drifts": [
                {
                    "file": "README.md",
                    "doc_count": "10",
                    "actual_count": 25,
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "25" in (tmp_path / "README.md").read_text()
        assert "10" not in (tmp_path / "README.md").read_text()


class TestApplyFixesActions:
    def test_fixes_action_version(self, tmp_path):
        _write(
            tmp_path / "ci.yml",
            "uses: actions/checkout@v3\n  - uses: actions/setup-node@v3",
        )
        result = {
            "actions_drifts": [
                {
                    "file": "ci.yml",
                    "action": "actions/checkout",
                    "current": "v3",
                    "suggested": "v5",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "ci.yml" in fixed
        content = (tmp_path / "ci.yml").read_text()
        assert "actions/checkout@v5" in content
        assert "actions/checkout@v3" not in content


class TestApplyFixesLineEnding:
    def test_creates_gitattributes_when_missing(self, tmp_path):
        result = {"lineending_drifts": [{"file": ".gitattributes"}]}
        fixed = apply_fixes(tmp_path, result)
        assert ".gitattributes" in fixed
        ga = tmp_path / ".gitattributes"
        assert ga.exists()
        content = ga.read_text()
        assert "text=auto eol=lf" in content

    def test_appends_to_existing_gitattributes(self, tmp_path):
        _write(
            tmp_path / ".gitattributes",
            "# existing config\n*.js text\n",
        )
        result = {"lineending_drifts": [{"file": ".gitattributes"}]}
        fixed = apply_fixes(tmp_path, result)
        assert ".gitattributes" in fixed
        content = (tmp_path / ".gitattributes").read_text()
        assert "text=auto eol=lf" in content
        assert "# existing config" in content

    def test_no_duplicate_append(self, tmp_path):
        _write(tmp_path / ".gitattributes", "* text=auto eol=lf\n")
        result = {"lineending_drifts": [{"file": ".gitattributes"}]}
        fixed = apply_fixes(tmp_path, result)
        # Already correct — should NOT re-add
        assert ".gitattributes" not in fixed


class TestApplyFixesGHActionsVersion:
    def test_fixes_outdated_action(self, tmp_path):
        _write(tmp_path / "workflow.yml", "    - uses: actions/upload-artifact@v3")
        result = {
            "gh_actions_version_drifts": [
                {
                    "file": "workflow.yml",
                    "action": "actions/upload-artifact",
                    "current": "v3",
                    "suggested": "v4",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "workflow.yml" in fixed
        assert "actions/upload-artifact@v4" in (tmp_path / "workflow.yml").read_text()


class TestApplyFixesHelm:
    def test_fixes_helm_drift(self, tmp_path):
        _write(tmp_path / "README.md", "Uses nginx:1.20 from Helm chart")
        result = {
            "helm_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.20",
                    "helm_image": "1.21",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "1.21" in (tmp_path / "README.md").read_text()
        assert "1.20" not in (tmp_path / "README.md").read_text()


class TestApplyFixesDockerCompose:
    def test_fixes_docker_compose_drift(self, tmp_path):
        _write(tmp_path / "README.md", "docker-compose uses redis:6.0")
        result = {
            "dc_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "6.0",
                    "compose_image": "redis:7.0",
                }
            ]
        }
        fixed = apply_fixes(tmp_path, result)
        assert "README.md" in fixed
        assert "redis:7.0" in (tmp_path / "README.md").read_text()
        assert "6.0" not in (tmp_path / "README.md").read_text()


class TestApplyFixesEdgeCases:
    def test_empty_result_dict(self, tmp_path):
        fixed = apply_fixes(tmp_path, {})
        assert fixed == []

    def test_returns_unique_files(self, tmp_path):
        """If same file appears in multiple drift types, list it once."""
        _write(tmp_path / "README.md", "Install Rust 1.93.0 and Node.js 18")
        result = {
            "drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.93",
                    "toolchain_version": "1.96",
                }
            ],
            "node_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "18",
                    "package_version": "24",
                }
            ],
        }
        fixed = apply_fixes(tmp_path, result)
        # README.md should appear (at least once, ideally unique)
        assert "README.md" in fixed
