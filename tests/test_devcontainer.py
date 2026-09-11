"""Tests for Devcontainer drift detector."""
from driftcheck.detectors.devcontainer import (
    parse_devcontainer_image,
    parse_devcontainer_features,
    find_devcontainer_drift,
)


class TestParseDevcontainerImage:
    def test_simple_image(self):
        text = '{"image": "mcr.microsoft.com/devcontainers/rust:1"}'
        assert parse_devcontainer_image(text) == "mcr.microsoft.com/devcontainers/rust:1"

    def test_no_image(self):
        text = '{"features": {}}'
        assert parse_devcontainer_image(text) is None

    def test_invalid_json(self):
        assert parse_devcontainer_image("not json") is None

    def test_empty(self):
        assert parse_devcontainer_image("") is None

    def test_build_dockerfile(self):
        text = '{"build": {"dockerfile": "Dockerfile"}}'
        assert parse_devcontainer_image(text) == "Dockerfile"


class TestParseDevcontainerFeatures:
    def test_empty(self):
        assert parse_devcontainer_features("") == {}

    def test_no_features(self):
        assert parse_devcontainer_features('{"image": "foo"}') == {}

    def test_features_with_versions(self):
        text = '{"features": {"ghcr.io/devcontainers/features/docker-in-docker:2": {"version": "20.10"}}}'
        result = parse_devcontainer_features(text)
        assert "ghcr.io/devcontainers/features/docker-in-docker:2" in result

    def test_features_with_string_values(self):
        text = '{"features": {"ghcr.io/devcontainers/features/docker-in-docker:2": "latest"}}'
        result = parse_devcontainer_features(text)
        assert "ghcr.io/devcontainers/features/docker-in-docker:2" in result


class TestFindDevcontainerDrift:
    def test_no_devcontainer(self):
        assert find_devcontainer_drift("", {"README.md": "container"}) == []

    def test_no_drift(self):
        dc = '{"image": "rust:1.70", "features": {}}'
        docs = {"README.md": "Dev Container uses rust:1.70"}
        assert find_devcontainer_drift(dc, docs) == []

    def test_drift_image_version(self):
        dc = '{"image": "rust:1.70", "features": {}}'
        docs = {"README.md": "Uses rust 1.68 in devcontainer"}
        drifts = find_devcontainer_drift(dc, docs)
        assert len(drifts) >= 1
        assert drifts[0]["doc_version"] == "1.68"

    def test_empty_docs(self):
        dc = '{"features": {"docker": {"version": "20.10"}}}'
        assert find_devcontainer_drift(dc, {}) == []
