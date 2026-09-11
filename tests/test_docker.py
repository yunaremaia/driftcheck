"""Tests for Docker drift detector."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.docker import (
    parse_dockerfile_from,
    find_docker_drift,
)


class TestParseDockerfileImages:
    def test_single_from(self):
        text = "FROM node:20-slim"
        result = parse_dockerfile_from(text)
        assert result == {"node": "20-slim"}

    def test_multiple_from(self):
        text = "FROM node:20-slim\nFROM nginx:1.21"
        result = parse_dockerfile_from(text)
        assert result == {"node": "20-slim", "nginx": "1.21"}

    def test_empty(self):
        assert parse_dockerfile_from("") == {}

    def test_no_from(self):
        text = "RUN echo hello"
        assert parse_dockerfile_from(text) == {}


class TestFindDockerDrift:
    def test_drift_detected(self):
        dockerfiles = {"Dockerfile": "FROM node:20-slim"}
        docs = {"README.md": "Docker node:18"}
        result = find_docker_drift(dockerfiles, docs)
        assert len(result) >= 1

    def test_no_drift(self):
        dockerfiles = {"Dockerfile": "FROM node:20-slim"}
        docs = {"README.md": "Docker node:20"}
        assert find_docker_drift(dockerfiles, docs) == []

    def test_empty_dockerfiles(self):
        assert find_docker_drift({}, {"README.md": "Node 20"}) == []
