"""Tests for lockfile drift detection: missing, stale, or orphaned lockfiles."""
from __future__ import annotations
import os
import tempfile
import time
from pathlib import Path

import pytest

from driftcheck.detectors.lockfile import find_lockfile_drift


class TestFindLockfileDrift:
    def test_missing_package_lock(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_missing"
        assert "package-lock.json" in result[0]["detail"]

    def test_missing_cargo_lock(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_missing"
        assert "Cargo.lock" in result[0]["detail"]

    def test_missing_go_sum(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/foo")
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_missing"
        assert "go.sum" in result[0]["detail"]

    def test_missing_gemfile_lock(self, tmp_path):
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_missing"
        assert "Gemfile.lock" in result[0]["detail"]

    def test_missing_composer_lock(self, tmp_path):
        (tmp_path / "composer.json").write_text('{"name": "test"}')
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_missing"
        assert "composer.lock" in result[0]["detail"]

    def test_no_drift_when_lockfile_exists(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "package-lock.json").write_text('{"name": "test"}')
        result = find_lockfile_drift(tmp_path)
        # No missing lockfile drift (may have stale check)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_orphaned_lockfile(self, tmp_path):
        (tmp_path / "package-lock.json").write_text('{"name": "test"}')
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_orphaned"
        assert "package-lock.json" in result[0]["file"]

    def test_orphaned_cargo_lock(self, tmp_path):
        (tmp_path / "Cargo.lock").write_text('[metadata]')
        result = find_lockfile_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lockfile_orphaned"

    def test_stale_lockfile(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "package-lock.json").write_text('{"name": "test"}')
        # Make package.json newer than package-lock.json
        pkg_json = tmp_path / "package.json"
        lock_json = tmp_path / "package-lock.json"
        # Set lockfile mtime to past
        past_time = time.time() - 3600
        os.utime(lock_json, (past_time, past_time))
        # Set package.json mtime to now
        os.utime(pkg_json, None)
        result = find_lockfile_drift(tmp_path)
        stale = [r for r in result if r["kind"] == "lockfile_stale"]
        assert len(stale) == 1
        assert "package-lock.json" in stale[0]["file"]

    def test_empty_repo(self, tmp_path):
        result = find_lockfile_drift(tmp_path)
        assert result == []

    def test_multiple_manifests(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        (tmp_path / "go.mod").write_text("module example.com/foo")
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 3

    def test_yarn_lock_accepted(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "yarn.lock").write_text('# yarn lockfile v1')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_pnpm_lock_accepted(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "pnpm-lock.yaml").write_text('lockfileVersion: 5.4')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_bun_lock_accepted(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "bun.lock").write_text('{}')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_poetry_lock_accepted(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "test"')
        (tmp_path / "poetry.lock").write_text('[[package]]')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_uv_lock_accepted(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"')
        (tmp_path / "uv.lock").write_text('version = 1')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0

    def test_pipfile_lock_accepted(self, tmp_path):
        (tmp_path / "Pipfile").write_text('[[source]]\nurl = "https://pypi.org"')
        (tmp_path / "Pipfile.lock").write_text('{}')
        result = find_lockfile_drift(tmp_path)
        missing = [r for r in result if r["kind"] == "lockfile_missing"]
        assert len(missing) == 0
