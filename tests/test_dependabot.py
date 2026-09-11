"""Tests for Dependabot drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.dependabot import find_dependabot_drift


class TestFindDependabotDrift:
    def test_missing_dependabot(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = find_dependabot_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "dependabot_missing"
        assert "npm" in result[0]["ecosystems"]

    def test_incomplete_dependabot(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "requirements.txt").write_text("requests==2.28")
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            'version: 2\nupdates:\n  - package-ecosystem: "npm"\n    directory: "/"\n'
        )
        result = find_dependabot_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "dependabot_incomplete"
        assert "pip" in result[0]["ecosystems"]

    def test_no_drift(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            'version: 2\nupdates:\n  - package-ecosystem: "npm"\n    directory: "/"\n'
        )
        result = find_dependabot_drift(tmp_path)
        assert result == []

    def test_empty_repo(self, tmp_path):
        result = find_dependabot_drift(tmp_path)
        assert result == []
