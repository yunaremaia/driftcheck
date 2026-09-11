"""Tests for GitLab CI drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.gitlab import (
    parse_gitlab_images,
    find_gitlab_drift,
)


class TestParseGitlabCiImages:
    def test_single_image(self):
        text = "image: node:20"
        result = parse_gitlab_images(text)
        assert result == {"node": "20"}

    def test_multiple_images(self):
        text = "image: node:20\njob:\n  image: python:3.11"
        result = parse_gitlab_images(text)
        assert "node" in result or "python" in result

    def test_empty(self):
        assert parse_gitlab_images("") == {}


class TestFindGitlabCiDrift:
    def test_drift_detected(self):
        gitlab = {"gitlab-ci.yml": "image: node:20"}
        docs = {"README.md": "image node:18"}
        result = find_gitlab_drift(gitlab, docs)
        assert len(result) >= 1

    def test_no_drift(self):
        gitlab = {"gitlab-ci.yml": "image: node:20"}
        docs = {"README.md": "image node:20"}
        assert find_gitlab_drift(gitlab, docs) == []
