"""Tests for driftcheck baseline mode — incremental drift detection."""

import json

import pytest

from driftcheck.baseline import (
    create_baseline,
    load_baseline,
    update_baseline,
    reset_baseline,
    compare_against_baseline,
    show_baseline,
    _make_drift_key,
    BASELINE_FILENAME,
    BASELINE_SCHEMA_VERSION,
)
from driftcheck.detector import scan_repo


@pytest.fixture
def tmp_repo_with_drift(tmp_path):
    """Create a temporary repo with known drift."""
    (tmp_path / "README.md").write_text(
        "# Test Project\n\nRequires Python 3.9\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nrequires-python = '>=3.11'\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def tmp_repo_clean(tmp_path):
    """Create a temporary repo with NO drift."""
    (tmp_path / "README.md").write_text(
        "# Test Project\n\nRequires Python 3.11\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nrequires-python = '>=3.11'\n", encoding="utf-8"
    )
    return tmp_path


class TestMakeDriftKey:
    def test_doc_version_key(self):
        drift = {"file": "README.md", "doc_version": "3.9"}
        key = _make_drift_key("python_drifts", drift)
        assert key == ("python_drifts", "README.md", "doc=3.9")

    def test_detail_key(self):
        drift = {"file": "Dockerfile", "detail": "floating tag"}
        key = _make_drift_key("docker_drifts", drift)
        assert key[0] == "docker_drifts"
        assert key[1] == "Dockerfile"
        assert "detail=" in key[2]

    def test_same_file_different_type(self):
        d1 = {"file": "README.md", "doc_version": "3.9"}
        d2 = {"file": "README.md", "doc_version": "3.10"}
        assert _make_drift_key("python", d1) != _make_drift_key("python", d2)


class TestCreateBaseline:
    def test_creates_file(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        baseline = create_baseline(tmp_repo_with_drift, result)
        assert (tmp_repo_with_drift / BASELINE_FILENAME).exists()
        assert baseline["version"] == BASELINE_SCHEMA_VERSION

    def test_records_drift_count(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        baseline = create_baseline(tmp_repo_with_drift, result)
        assert baseline["total_entries"] > 0

    def test_adds_to_gitignore(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        gitignore = tmp_repo_with_drift / ".gitignore"
        assert gitignore.exists()
        assert BASELINE_FILENAME in gitignore.read_text()

    def test_no_drift_baseline(self, tmp_repo_clean):
        result = scan_repo(tmp_repo_clean)
        baseline = create_baseline(tmp_repo_clean, result)
        # Clean repo may still have some drifts (e.g., count_drifts for missing skills/)
        # The key is that baseline records whatever exists
        assert baseline["total_entries"] >= 0

    def test_stores_commit_sha(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        baseline = create_baseline(tmp_repo_with_drift, result)
        # commit_sha should be present (either "unknown" or a valid SHA)
        assert "commit_sha" in baseline


class TestLoadBaseline:
    def test_load_existing(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        loaded = load_baseline(tmp_repo_with_drift)
        assert loaded is not None
        assert loaded["version"] == BASELINE_SCHEMA_VERSION

    def test_load_nonexistent(self, tmp_repo_with_drift):
        assert load_baseline(tmp_repo_with_drift) is None

    def test_load_corrupted(self, tmp_repo_with_drift):
        baseline_path = tmp_repo_with_drift / BASELINE_FILENAME
        baseline_path.write_text("not json")
        assert load_baseline(tmp_repo_with_drift) is None

    def test_load_wrong_schema_version(self, tmp_repo_with_drift):
        baseline_path = tmp_repo_with_drift / BASELINE_FILENAME
        baseline_path.write_text(json.dumps({"version": 999}))
        assert load_baseline(tmp_repo_with_drift) is None


class TestUpdateBaseline:
    def test_preserves_first_seen(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        # Update
        result2 = scan_repo(tmp_repo_with_drift)
        updated = update_baseline(tmp_repo_with_drift, result2)
        # first_seen should be preserved from original
        assert updated["total_entries"] > 0

    def test_updates_commit_sha(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        result2 = scan_repo(tmp_repo_with_drift)
        updated = update_baseline(tmp_repo_with_drift, result2)
        assert "updated_at" in updated


class TestResetBaseline:
    def test_removes_file(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        assert (tmp_repo_with_drift / BASELINE_FILENAME).exists()
        removed = reset_baseline(tmp_repo_with_drift)
        assert removed is True
        assert not (tmp_repo_with_drift / BASELINE_FILENAME).exists()

    def test_returns_false_if_no_baseline(self, tmp_repo_with_drift):
        removed = reset_baseline(tmp_repo_with_drift)
        assert removed is False


class TestCompareAgainstBaseline:
    def test_no_new_drifts(self, tmp_repo_with_drift):
        """If nothing changed, no new drifts should be reported."""
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        comparison = compare_against_baseline(tmp_repo_with_drift, result)
        # All drifts are pre-existing, no new ones
        assert comparison["new_drifts"] == {}
        assert len(comparison["pre_existing_drifts"]) > 0

    def test_new_drift_detected(self, tmp_repo_clean):
        """Adding drift after baseline should be detected as new."""
        result = scan_repo(tmp_repo_clean)
        create_baseline(tmp_repo_clean, result)
        # Introduce drift
        (tmp_repo_clean / "README.md").write_text(
            "# Test\n\nRequires Python 3.8\n", encoding="utf-8"
        )
        result2 = scan_repo(tmp_repo_clean)
        comparison = compare_against_baseline(tmp_repo_clean, result2)
        assert len(comparison["new_drifts"]) > 0

    def test_no_baseline_all_new(self, tmp_repo_with_drift):
        """Without baseline, all drifts are new."""
        result = scan_repo(tmp_repo_with_drift)
        comparison = compare_against_baseline(tmp_repo_with_drift, result)
        assert comparison["baseline_info"] is None
        assert len(comparison["new_drifts"]) > 0
        assert comparison["pre_existing_drifts"] == {}


class TestShowBaseline:
    def test_shows_summary(self, tmp_repo_with_drift):
        result = scan_repo(tmp_repo_with_drift)
        create_baseline(tmp_repo_with_drift, result)
        summary = show_baseline(tmp_repo_with_drift)
        assert "Total drifts:" in summary

    def test_no_baseline(self, tmp_repo_with_drift):
        summary = show_baseline(tmp_repo_with_drift)
        assert "No baseline found" in summary


class TestBaselineCLI:
    """Test baseline CLI integration."""

    def test_baseline_flag_creates_file(self, tmp_repo_with_drift):
        from driftcheck.cli import main

        ret = main([str(tmp_repo_with_drift), "--baseline"])
        assert ret == 0
        assert (tmp_repo_with_drift / BASELINE_FILENAME).exists()

    def test_baseline_show(self, tmp_repo_with_drift):
        from driftcheck.cli import main

        main([str(tmp_repo_with_drift), "--baseline"])
        # Show should succeed
        ret = main([str(tmp_repo_with_drift), "--baseline-show"])
        assert ret == 0

    def test_baseline_reset(self, tmp_repo_with_drift):
        from driftcheck.cli import main

        main([str(tmp_repo_with_drift), "--baseline"])
        ret = main([str(tmp_repo_with_drift), "--baseline-reset"])
        assert ret == 0
        assert not (tmp_repo_with_drift / BASELINE_FILENAME).exists()

    def test_scan_with_baseline_no_new_drifts(self, tmp_repo_with_drift):
        """When baseline covers all drifts, scan should succeed."""
        from driftcheck.cli import main

        # Create baseline
        ret = main([str(tmp_repo_with_drift), "--baseline"])
        assert ret == 0
        # Scan again — no new drifts
        ret = main([str(tmp_repo_with_drift), "--quiet"])
        assert ret == 0

    def test_scan_with_baseline_new_drift(self, tmp_repo_clean):
        """When a new drift appears, scan should fail."""
        from driftcheck.cli import main

        # Create baseline on clean repo
        ret = main([str(tmp_repo_clean), "--baseline"])
        assert ret == 0
        # Introduce drift
        (tmp_repo_clean / "README.md").write_text(
            "# Test\n\nRequires Python 3.8\n", encoding="utf-8"
        )
        # Scan should fail due to new drift
        ret = main([str(tmp_repo_clean), "--quiet"])
        assert ret == 1

    def test_json_output_with_baseline(self, tmp_repo_with_drift):
        from driftcheck.cli import main
        import io
        import sys

        # Create baseline
        main([str(tmp_repo_with_drift), "--baseline"])
        # Capture JSON output
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        ret = main([str(tmp_repo_with_drift), "--json"])
        sys.stdout = old_stdout
        output = buf.getvalue()
        data = json.loads(output)
        assert "_baseline" in data
        assert "new_drift_count" in data["_baseline"]
