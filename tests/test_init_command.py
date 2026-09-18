"""Tests for `driftcheck init` subcommand."""
import tempfile
from pathlib import Path
from driftcheck.cli import _detect_detectors, _generate_init_config, _detect_project_files


def test_detect_detectors_empty_repo():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        detected = _detect_detectors(root)
        assert detected == []


def test_detect_detectors_rust_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\nversion = '0.1.0'\n")
        detected = _detect_detectors(root)
        assert "rust_drifts" in detected


def test_detect_detectors_node_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"name": "test"}')
        detected = _detect_detectors(root)
        assert "node_drifts" in detected
        assert "bun_drifts" in detected


def test_detect_detectors_python_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\nrequires-python = '>=3.11'\n")
        detected = _detect_detectors(root)
        assert "python_drifts" in detected


def test_detect_detectors_go_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "go.mod").write_text("module test\ngo 1.21\n")
        detected = _detect_detectors(root)
        assert "go_drifts" in detected


def test_detect_detectors_docker_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Dockerfile").write_text("FROM python:3.11\n")
        detected = _detect_detectors(root)
        assert "docker_drifts" in detected


def test_detect_detectors_ci_workflows():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\non: push\n")
        detected = _detect_detectors(root)
        assert "actions_drifts" in detected
        assert "gh_actions_version_drifts" in detected


def test_detect_detectors_version_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".node-version").write_text("20.11.0\n")
        detected = _detect_detectors(root)
        assert "node_version_drifts" in detected


def test_generate_init_config_empty_repo():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "No project-specific files detected" in config


def test_generate_init_config_rust_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\nversion = '0.1.0'\n")
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "rust" in config.lower()
        assert "Cargo.toml" in config


def test_generate_init_config_node_project():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"name": "test"}')
        config = _generate_init_config(root)
        assert "[driftcheck]" in config
        assert "package.json" in config


def test_detect_project_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text("[package]\nname = 'test'\n")
        (root / "package.json").write_text('{"name": "test"}')
        files = _detect_project_files(root)
        assert "Cargo.toml" in files
        assert "package.json" in files


def test_detect_project_files_empty():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        files = _detect_project_files(root)
        assert files == []
