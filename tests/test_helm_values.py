"""Tests for Helm values drift detection."""
from pathlib import Path
import tempfile

from driftcheck.detectors.env_drift import find_helm_values_drift


class TestFindHelmValuesDrift:
    def test_no_values_file(self, tmp_path):
        assert find_helm_values_drift(tmp_path) == []

    def test_no_env_values_files(self, tmp_path):
        (tmp_path / "values.yaml").write_text("replicaCount: 1\ntag: 1.25")
        assert find_helm_values_drift(tmp_path) == []

    def test_drift_detected(self, tmp_path):
        (tmp_path / "values.yaml").write_text("replicaCount: 1\ntag: 1.25")
        (tmp_path / "values.prod.yaml").write_text("replicaCount: 3\ntag: 1.26")
        drifts = find_helm_values_drift(tmp_path)
        assert len(drifts) >= 1
        assert any("replicaCount" in d.get("key", "") for d in drifts)

    def test_no_drift_same_values(self, tmp_path):
        (tmp_path / "values.yaml").write_text("replicaCount: 1\ntag: 1.25")
        (tmp_path / "values.prod.yaml").write_text("replicaCount: 1\ntag: 1.25")
        assert find_helm_values_drift(tmp_path) == []
