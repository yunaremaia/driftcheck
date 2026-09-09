"""Tests for Helm drift detection: Chart.yaml/values.yaml image tags vs README."""
from pathlib import Path
import tempfile

from driftcheck.detectors.helm import (
    parse_helm_images,
    find_helm_drift,
    HELM_IMAGE_RE,
    HELM_VER_RE,
)


class TestParseHelmImages:
    def test_basic_image_tag(self):
        text = "image: nginx\n  tag: 1.25\n"
        result = parse_helm_images(text)
        assert result == {"nginx": "1.25"}

    def test_multiple_images(self):
        text = "image: nginx\n  tag: 1.25\nimage: redis\n  tag: 7.0\n"
        result = parse_helm_images(text)
        assert result == {"nginx": "1.25", "redis": "7.0"}

    def test_no_images(self):
        text = "replicaCount: 3\n"
        assert parse_helm_images(text) == {}

    def test_empty_string(self):
        assert parse_helm_images("") == {}

    def test_image_with_registry(self):
        text = "image: ghcr.io/myorg/app\n  tag: v2.0.0\n"
        result = parse_helm_images(text)
        assert result == {"ghcr.io/myorg/app": "v2.0.0"}


class TestFindHelmDrift:
    def test_no_drift(self):
        helm_files = {"values.yaml": "image: nginx\n  tag: 1.25\n"}
        docs = {"README.md": "Uses nginx:1.25"}
        assert find_helm_drift(helm_files, docs) == []

    def test_drift_detected(self):
        helm_files = {"values.yaml": "image: nginx\n  tag: 1.25\n"}
        docs = {"README.md": "Uses nginx:1.24"}
        drifts = find_helm_drift(helm_files, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_version"] == "nginx:1.24"
        assert drifts[0]["helm_image"] == "nginx:1.25"

    def test_no_helm_files(self):
        assert find_helm_drift({}, {"README.md": "nginx:1.25"}) == []

    def test_no_docs(self):
        helm_files = {"values.yaml": "image: nginx\n  tag: 1.25\n"}
        assert find_helm_drift(helm_files, {}) == []

    def test_tag_with_suffix_matches(self):
        """Verify '24' in docs matches '24-slim' in helm (suffix handling)."""
        helm_files = {"values.yaml": "image: nginx\n  tag: 24-slim\n"}
        docs = {"README.md": "Uses nginx:24"}
        assert find_helm_drift(helm_files, docs) == []

    def test_multiple_images_any_drift(self):
        helm_files = {"values.yaml": "image: nginx\n  tag: 1.25\nimage: redis\n  tag: 7.0\n"}
        docs = {"README.md": "redis:6.2"}
        drifts = find_helm_drift(helm_files, docs)
        assert len(drifts) == 1

    def test_helm_file_key_chart_yaml(self):
        helm_files = {"Chart.yaml": "image: myapp\n  tag: v1.0.0\n"}
        docs = {"README.md": "myapp:v0.9.0"}
        drifts = find_helm_drift(helm_files, docs)
        assert len(drifts) == 1

    def test_no_image_in_docs(self):
        helm_files = {"values.yaml": "image: nginx\n  tag: 1.25\n"}
        docs = {"README.md": "A great application"}
        assert find_helm_drift(helm_files, docs) == []
