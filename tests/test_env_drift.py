"""Tests for environment drift detection (.env, Docker Compose overrides, Helm values)."""
import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.env_drift import (
    parse_env_file,
    parse_env_example,
    find_env_drift,
    find_compose_override_drift,
    find_helm_values_drift,
    find_env_drift_combined,
)


class TestParseEnvFile:
    def test_basic_parsing(self):
        text = "DATABASE_URL=postgres://localhost\nAPI_KEY=secret123\n"
        result = parse_env_file(text)
        assert result == {"DATABASE_URL": "postgres://localhost", "API_KEY": "secret123"}

    def test_comments_ignored(self):
        text = "# This is a comment\nDATABASE_URL=postgres://localhost\n"
        result = parse_env_file(text)
        assert result == {"DATABASE_URL": "postgres://localhost"}

    def test_empty_lines_ignored(self):
        text = "DATABASE_URL=postgres://localhost\n\n\nAPI_KEY=secret\n"
        result = parse_env_file(text)
        assert result == {"DATABASE_URL": "postgres://localhost", "API_KEY": "secret"}

    def test_quoted_values(self):
        text = 'DATABASE_URL="postgres://localhost"\nAPI_KEY=\'secret123\'\n'
        result = parse_env_file(text)
        assert result == {"DATABASE_URL": "postgres://localhost", "API_KEY": "secret123"}

    def test_empty_file(self):
        assert parse_env_file("") == {}

    def test_no_env_file(self, tmp_path):
        assert find_env_drift(tmp_path) == []


class TestFindEnvDrift:
    def test_no_env_example(self, tmp_path):
        """No .env.example means no drift."""
        assert find_env_drift(tmp_path) == []

    def test_env_missing_keys(self, tmp_path):
        """Keys in .env.example missing from .env."""
        (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\nREDIS_URL=\n")
        (tmp_path / ".env").write_text("DATABASE_URL=postgres://localhost\n")
        drifts = find_env_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "env_missing_keys"
        assert "API_KEY" in drifts[0]["keys"]
        assert "REDIS_URL" in drifts[0]["keys"]

    def test_env_extra_keys(self, tmp_path):
        """Keys in .env not in .env.example."""
        (tmp_path / ".env.example").write_text("DATABASE_URL=\n")
        (tmp_path / ".env").write_text("DATABASE_URL=postgres\nEXTRA_KEY=value\n")
        drifts = find_env_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "env_extra_keys"
        assert "EXTRA_KEY" in drifts[0]["keys"]

    def test_env_file_missing(self, tmp_path):
        """Only .env.example exists, .env missing."""
        (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\n")
        drifts = find_env_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "env_missing"

    def test_no_drift(self, tmp_path):
        """Both files have same keys."""
        (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\n")
        (tmp_path / ".env").write_text("DATABASE_URL=postgres\nAPI_KEY=secret\n")
        assert find_env_drift(tmp_path) == []


class TestFindComposeOverrideDrift:
    def test_no_compose_files(self, tmp_path):
        assert find_compose_override_drift(tmp_path) == []

    def test_no_override_files(self, tmp_path):
        """Only base compose file, no overrides."""
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n"
        )
        assert find_compose_override_drift(tmp_path) == []

    def test_image_tag_drift(self, tmp_path):
        """Override file has different image tag."""
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n"
        )
        (tmp_path / "docker-compose.prod.yml").write_text(
            "services:\n  web:\n    image: nginx:1.26\n"
        )
        drifts = find_compose_override_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "compose_image_drift"
        assert drifts[0]["base_image"] == "nginx:1.25"
        assert drifts[0]["override_image"] == "nginx:1.26"

    def test_no_drift_same_image(self, tmp_path):
        """Override file has same image tag."""
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n"
        )
        (tmp_path / "docker-compose.prod.yml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n"
        )
        assert find_compose_override_drift(tmp_path) == []


class TestFindHelmValuesDrift:
    def test_no_values_file(self, tmp_path):
        assert find_helm_values_drift(tmp_path) == []

    def test_no_env_values_files(self, tmp_path):
        """Only values.yaml, no environment-specific files."""
        (tmp_path / "values.yaml").write_text("replicaCount: 2\ntag: 1.0.0\n")
        assert find_helm_values_drift(tmp_path) == []

    def test_replica_count_drift(self, tmp_path):
        """Environment-specific values file has different replicaCount."""
        (tmp_path / "values.yaml").write_text("replicaCount: 2\ntag: 1.0.0\n")
        (tmp_path / "values.prod.yaml").write_text("replicaCount: 5\ntag: 1.0.0\n")
        drifts = find_helm_values_drift(tmp_path)
        assert len(drifts) >= 1
        replica_drifts = [d for d in drifts if d.get("key") == "replicaCount"]
        assert len(replica_drifts) == 1
        assert replica_drifts[0]["base_value"] == "2"
        assert replica_drifts[0]["env_value"] == "5"

    def test_tag_drift(self, tmp_path):
        """Environment-specific values file has different tag."""
        (tmp_path / "values.yaml").write_text("replicaCount: 2\ntag: 1.0.0\n")
        (tmp_path / "values.prod.yaml").write_text("replicaCount: 2\ntag: 2.0.0\n")
        drifts = find_helm_values_drift(tmp_path)
        tag_drifts = [d for d in drifts if d.get("key") == "tag"]
        assert len(tag_drifts) == 1
        assert tag_drifts[0]["base_value"] == "1.0.0"
        assert tag_drifts[0]["env_value"] == "2.0.0"


class TestFindEnvDriftCombined:
    def test_combined_no_drift(self, tmp_path):
        """No drift in any category."""
        assert find_env_drift_combined(tmp_path) == []

    def test_combined_multiple_drifts(self, tmp_path):
        """Multiple drift types detected."""
        # .env.example vs .env drift
        (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\n")
        (tmp_path / ".env").write_text("DATABASE_URL=postgres\n")
        
        # Compose override drift
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n"
        )
        (tmp_path / "docker-compose.prod.yml").write_text(
            "services:\n  web:\n    image: nginx:1.26\n"
        )
        
        drifts = find_env_drift_combined(tmp_path)
        kinds = {d["kind"] for d in drifts}
        assert "env_missing_keys" in kinds
        assert "compose_image_drift" in kinds


class TestEnvDriftIntegration:
    def test_env_drift_in_scan_repo(self, tmp_path):
        """env_drifts key appears in scan_repo output."""
        from driftcheck.detector import scan_repo
        
        (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\n")
        (tmp_path / ".env").write_text("DATABASE_URL=postgres\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        
        result = scan_repo(tmp_path)
        assert "env_drifts" in result
        assert len(result["env_drifts"]) > 0
