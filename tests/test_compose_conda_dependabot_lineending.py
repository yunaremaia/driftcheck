"""Tests for Docker Compose, Conda, Dependabot, and lineending drift detectors."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.compose import (
    parse_docker_compose_images,
    find_docker_compose_drift,
)
from driftcheck.detectors.conda import (
    parse_conda_environment,
    find_conda_drift,
)
from driftcheck.detectors.dependabot import find_dependabot_drift
from driftcheck.detectors.lineending import find_lineending_drift


# ---- Docker Compose ----

class TestParseDockerComposeImages:
    def test_single_image(self):
        text = "    image: nginx:1.21"
        result = parse_docker_compose_images(text)
        assert result == {"nginx": "1.21"}

    def test_multiple_images(self):
        text = "    image: nginx:1.21\n    image: redis:7.0"
        result = parse_docker_compose_images(text)
        assert result == {"nginx": "1.21", "redis": "7.0"}

    def test_empty(self):
        assert parse_docker_compose_images("") == {}

    def test_no_match(self):
        text = "version: '3.8'\nservices:\n  web:\n    build: ."
        assert parse_docker_compose_images(text) == {}


class TestFindDockerComposeDrift:
    def test_drift_detected(self):
        dc = {"docker-compose.yml": "    image: nginx:1.21"}
        docs = {"README.md": "Uses nginx:1.20"}
        result = find_docker_compose_drift(dc, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "nginx:1.20"
        assert result[0]["compose_image"] == "nginx:1.21"

    def test_no_drift(self):
        dc = {"docker-compose.yml": "    image: nginx:1.21"}
        docs = {"README.md": "Uses nginx:1.21"}
        assert find_docker_compose_drift(dc, docs) == []

    def test_no_compose_images(self):
        dc = {"docker-compose.yml": "version: '3.8'"}
        docs = {"README.md": "Uses nginx:1.20"}
        assert find_docker_compose_drift(dc, docs) == []

    def test_empty_docs(self):
        dc = {"docker-compose.yml": "    image: nginx:1.21"}
        assert find_docker_compose_drift(dc, {}) == []


# ---- Conda ----

class TestParseCondaEnvironment:
    def test_pinned_packages(self):
        text = "dependencies:\n  - python=3.10\n  - numpy>=1.24\n  - pandas==2.0"
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_conda_environment(f.name)
        assert "numpy" in result
        assert "pandas" in result

    def test_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("")
            f.flush()
            result = parse_conda_environment(f.name)
        assert result == {}


class TestFindCondaDrift:
    def test_unpinned_detected(self, tmp_path):
        (tmp_path / "environment.yml").write_text("dependencies:\n  - numpy\n  - pandas\n")
        result = find_conda_drift(str(tmp_path))
        assert len(result) >= 1
        assert result[0]["type"] == "conda_drift"

    def test_no_environment_yml(self, tmp_path):
        result = find_conda_drift(str(tmp_path))
        assert result == []


# ---- Dependabot ----

class TestFindDependabotDrift:
    def test_missing_dependabot(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = find_dependabot_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "dependabot_missing"
        assert "npm" in result[0]["ecosystems"]

    def test_incomplete_dependabot(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "requirements.txt").write_text("requests==2.28")
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            'version: 2\nupdates:\n  - package-ecosystem: "npm"\n    directory: "/"\n'
        )
        result = find_dependabot_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "dependabot_incomplete"
        assert "pip" in result[0]["ecosystems"]

    def test_no_drift(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            'version: 2\nupdates:\n  - package-ecosystem: "npm"\n    directory: "/"\n'
        )
        result = find_dependabot_drift(tmp_path)
        assert result == []

    def test_empty_repo(self, tmp_path):
        result = find_dependabot_drift(tmp_path)
        assert result == []


# ---- Lineending ----

class TestFindLineendingDrift:
    def test_missing_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        result = find_lineending_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lineending"
        assert "missing" in result[0]["detail"]

    def test_present_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = find_lineending_drift(tmp_path)
        assert result == []

    def test_incomplete_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / ".gitattributes").write_text("# just a comment\n")
        result = find_lineending_drift(tmp_path)
        assert len(result) == 1
        assert "does not set" in result[0]["detail"]

    def test_no_source_files(self, tmp_path):
        result = find_lineending_drift(tmp_path)
        assert result == []
