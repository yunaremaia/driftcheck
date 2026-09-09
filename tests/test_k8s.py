"""Tests for Kubernetes drift detection: image tags in manifests vs README."""
from pathlib import Path
import tempfile

from driftcheck.detectors.k8s import (
    parse_k8s_images,
    find_k8s_drift,
    K8S_IMAGE_RE,
    K8S_VER_RE,
)


class TestParseK8sImages:
    def test_basic_image_tag(self):
        text = "image: nginx:1.25\n"
        result = parse_k8s_images(text)
        assert result == {"nginx": "1.25"}

    def test_multiple_images(self):
        text = "image: nginx:1.25\nimage: redis:7.0\n"
        result = parse_k8s_images(text)
        assert result == {"nginx": "1.25", "redis": "7.0"}

    def test_no_images(self):
        text = "replicas: 3\n"
        assert parse_k8s_images(text) == {}

    def test_empty_string(self):
        assert parse_k8s_images("") == {}

    def test_image_with_registry(self):
        text = "image: ghcr.io/myorg/app:v2.0.0\n"
        result = parse_k8s_images(text)
        assert result == {"ghcr.io/myorg/app": "v2.0.0"}


class TestFindK8sDrift:
    def test_no_drift(self):
        k8s_files = {"deployment.yaml": "image: nginx:1.25\n"}
        docs = {"README.md": "Uses nginx:1.25"}
        assert find_k8s_drift(k8s_files, docs) == []

    def test_drift_detected(self):
        k8s_files = {"deployment.yaml": "image: nginx:1.25\n"}
        docs = {"README.md": "Uses nginx:1.24"}
        drifts = find_k8s_drift(k8s_files, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_image"] == "nginx:1.24"
        assert drifts[0]["k8s_image"] == "nginx:1.25"

    def test_no_k8s_files(self):
        assert find_k8s_drift({}, {"README.md": "nginx:1.25"}) == []

    def test_no_docs(self):
        k8s_files = {"deployment.yaml": "image: nginx:1.25\n"}
        assert find_k8s_drift(k8s_files, {}) == []

    def test_tag_with_suffix_matches(self):
        """Verify '24' in docs matches '24-slim' in k8s (suffix handling)."""
        k8s_files = {"deployment.yaml": "image: nginx:24-slim\n"}
        docs = {"README.md": "Uses nginx:24"}
        assert find_k8s_drift(k8s_files, docs) == []

    def test_multiple_images_any_drift(self):
        k8s_files = {"deployment.yaml": "image: nginx:1.25\nimage: redis:7.0\n"}
        docs = {"README.md": "redis:6.2"}
        drifts = find_k8s_drift(k8s_files, docs)
        assert len(drifts) == 1

    def test_no_image_in_docs(self):
        k8s_files = {"deployment.yaml": "image: nginx:1.25\n"}
        docs = {"README.md": "A great application"}
        assert find_k8s_drift(k8s_files, docs) == []
