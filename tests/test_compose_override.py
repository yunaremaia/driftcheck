"""Tests for Docker Compose override drift detection."""
from pathlib import Path
import tempfile

from driftcheck.detectors.env_drift import find_compose_override_drift


class TestFindComposeOverrideDrift:
    def test_no_compose_files(self, tmp_path):
        assert find_compose_override_drift(tmp_path) == []

    def test_no_override_files(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("image: nginx:1.25\nimage: redis:7")
        assert find_compose_override_drift(tmp_path) == []

    def test_drift_detected(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("image: nginx:1.25")
        (tmp_path / "docker-compose.prod.yml").write_text("image: nginx:1.26")
        drifts = find_compose_override_drift(tmp_path)
        assert len(drifts) == 1
        assert "nginx" in drifts[0]["detail"]

    def test_no_drift_same_version(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("image: nginx:1.25")
        (tmp_path / "docker-compose.prod.yml").write_text("image: nginx:1.25")
        assert find_compose_override_drift(tmp_path) == []
