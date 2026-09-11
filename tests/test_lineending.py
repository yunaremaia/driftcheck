"""Tests for Lineending drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.lineending import find_lineending_drift


class TestFindLineendingDrift:
    def test_missing_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        result = find_lineending_drift(tmp_path)
        assert len(result) == 1
        assert result[0]["kind"] == "lineending"
        assert "missing" in result[0]["detail"]

    def test_present_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
        result = find_lineending_drift(tmp_path)
        assert result == []

    def test_incomplete_gitattributes(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / ".gitattributes").write_text("# just a comment\n")
        result = find_lineending_drift(tmp_path)
        assert len(result) == 1
        assert "does not set" in result[0]["detail"]

    def test_no_source_files(self, tmp_path):
        result = find_lineending_drift(tmp_path)
        assert result == []
