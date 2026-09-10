"""Integration tests for CircleCI drift detection."""
from driftcheck.detectors.circleci import (
    parse_circleci_images,
    find_circleci_drift,
)


class TestParseCircleCIImages:
    def test_parse_image(self):
        config = "jobs:\n  build:\n    docker:\n      - image: cimg/node:18.0.0"
        images = parse_circleci_images(config)
        assert "cimg/node" in images
        assert images["cimg/node"] == "18.0.0"

    def test_empty_config(self):
        assert parse_circleci_images("") == {}


class TestFindCircleCIDrift:
    def test_drift_detected(self):
        circleci_files = {
            ".circleci/config.yml": "jobs:\n  build:\n    docker:\n      - image: cimg/node:18.0.0"
        }
        # The regex looks for "image" keyword before the image:tag pattern
        docs = {"README.md": "image: cimg/node:20.0.0"}
        drifts = find_circleci_drift(circleci_files, docs)
        assert len(drifts) >= 1

    def test_no_drift(self):
        circleci_files = {
            ".circleci/config.yml": "jobs:\n  build:\n    docker:\n      - image: cimg/node:20.0.0"
        }
        docs = {"README.md": "image: cimg/node:20.0.0"}
        drifts = find_circleci_drift(circleci_files, docs)
        assert drifts == []

    def test_ignores_non_docker_docs(self):
        circleci_files = {
            ".circleci/config.yml": "jobs:\n  build:\n    docker:\n      - image: cimg/node:18.0.0"
        }
        docs = {"README.md": "No docker or version mention"}
        drifts = find_circleci_drift(circleci_files, docs)
        assert drifts == []
