"""Tests for Docker Compose drift detector."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.compose import (
    parse_docker_compose_images,
    find_docker_compose_drift,
)


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
