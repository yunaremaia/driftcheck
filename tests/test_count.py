"""Tests for count drift detector: README 'N skills' vs actual filesystem count."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.count import find_count_drift, COUNT_RE


class TestCountRe:
    def test_simple_count(self):
        m = COUNT_RE.search("32 skills")
        assert m is not None
        assert m.group("count") == "32"

    def test_case_insensitive(self):
        m = COUNT_RE.search("10 SKILLS")
        assert m is not None
        assert m.group("count") == "10"

    def test_singular_skill(self):
        m = COUNT_RE.search("1 skill")
        assert m is not None
        assert m.group("count") == "1"

    def test_no_match(self):
        assert COUNT_RE.search("no count here") is None

    def test_multiple_matches(self):
        text = "We have 32 skills and 10 skills"
        matches = list(COUNT_RE.finditer(text))
        assert len(matches) == 2
        assert matches[0].group("count") == "32"
        assert matches[1].group("count") == "10"


class TestFindCountDrift:
    def test_drift_detected(self, tmp_path):
        # Create skills directory with 3 subdirectories
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "skill_a").mkdir()
        (skills / "skill_b").mkdir()
        (skills / "skill_c").mkdir()

        docs = {"README.md": "We have 32 skills"}
        result = find_count_drift(tmp_path, docs)
        assert len(result) == 1
        assert result[0]["doc_count"] == "32"
        assert result[0]["actual_count"] == 3

    def test_no_drift(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "skill_a").mkdir()
        (skills / "skill_b").mkdir()
        (skills / "skill_c").mkdir()

        docs = {"README.md": "We have 3 skills"}
        result = find_count_drift(tmp_path, docs)
        assert result == []

    def test_no_skills_dir(self, tmp_path):
        docs = {"README.md": "We have 32 skills"}
        result = find_count_drift(tmp_path, docs)
        assert result == []

    def test_empty_skills_dir(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()

        docs = {"README.md": "We have 32 skills"}
        result = find_count_drift(tmp_path, docs)
        assert result == []

    def test_skip_subset_mentions(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "skill_a").mkdir()
        (skills / "skill_b").mkdir()

        # "32 skills ship a scripts/_common.py" — subset, not total count
        docs = {"README.md": "32 skills ship a `scripts/_common.py`"}
        result = find_count_drift(tmp_path, docs)
        assert result == []

    def test_skip_use_mentions(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "skill_a").mkdir()

        docs = {"README.md": "32 skills use the same API"}
        result = find_count_drift(tmp_path, docs)
        assert result == []

    def test_multiple_files(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "a").mkdir()
        (skills / "b").mkdir()

        docs = {
            "README.md": "We have 10 skills",
            "CONTRIBUTING.md": "We have 2 skills"
        }
        result = find_count_drift(tmp_path, docs)
        assert len(result) == 1
        assert result[0]["file"] == "README.md"
        assert result[0]["doc_count"] == "10"

    def test_no_docs(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "a").mkdir()

        result = find_count_drift(tmp_path, {})
        assert result == []

    def test_files_in_skills_not_counted(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "skill_a").mkdir()
        (skills / "README.md").write_text("not a dir")

        docs = {"README.md": "We have 5 skills"}
        result = find_count_drift(tmp_path, docs)
        assert len(result) == 1
        assert result[0]["actual_count"] == 1
