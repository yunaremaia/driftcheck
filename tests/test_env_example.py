"""Tests for .env.example vs .env drift detection."""
import tempfile
from pathlib import Path

from driftcheck.detectors.env_drift import find_env_drift


class TestFindEnvDrift:
    def test_no_example_file(self, tmp_path):
        (tmp_path / ".env").write_text("DB_URL=postgres")
        assert find_env_drift(tmp_path) == []

    def test_env_missing_keys(self, tmp_path):
        (tmp_path / ".env.example").write_text("DB_URL=placeholder\nAPI_KEY=placeholder")
        (tmp_path / ".env").write_text("DB_URL=postgres")
        drifts = find_env_drift(tmp_path)
        assert len(drifts) == 1
        assert "API_KEY" in drifts[0]["detail"]

    def test_env_extra_keys(self, tmp_path):
        (tmp_path / ".env.example").write_text("DB_URL=placeholder")
        (tmp_path / ".env").write_text("DB_URL=postgres\nEXTRA_KEY=val")
        drifts = find_env_drift(tmp_path)
        assert any("EXTRA_KEY" in d["detail"] for d in drifts)

    def test_no_env_file(self, tmp_path):
        (tmp_path / ".env.example").write_text("DB_URL=placeholder\nAPI_KEY=placeholder")
        drifts = find_env_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "env_missing"

    def test_no_drift(self, tmp_path):
        (tmp_path / ".env.example").write_text("DB_URL=placeholder\nAPI_KEY=placeholder")
        (tmp_path / ".env").write_text("DB_URL=postgres\nAPI_KEY=secret")
        assert find_env_drift(tmp_path) == []
