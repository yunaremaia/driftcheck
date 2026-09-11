"""Tests for git tag drift detection."""
import tempfile
import os
import subprocess
from pathlib import Path
from driftcheck.detectors.git_tag import (
    get_latest_git_tag,
    find_git_tag_drift,
    parse_semver,
    SEMVER_RE,
)


def test_parse_semver_basic():
    assert parse_semver("1.2.3") == (1, 2, 3)


def test_parse_semver_no_patch():
    assert parse_semver("1.2") == (1, 2, 0)


def test_parse_semver_with_v_prefix():
    assert parse_semver("v1.2.3") == (1, 2, 3)


def test_parse_semver_invalid():
    assert parse_semver("abc") is None


def test_semver_re_match():
    assert SEMVER_RE.match("1.2.3")
    assert SEMVER_RE.match("v1.2.3")
    assert not SEMVER_RE.match("abc")


def test_get_latest_git_tag_with_tags():
    with tempfile.TemporaryDirectory() as td:
        # Initialize a git repo with tags
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=td, capture_output=True, check=True
        )
        # Create a file and commit
        (Path(td) / "test.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=td, capture_output=True, check=True
        )
        # Create tags
        subprocess.run(
            ["git", "tag", "v1.0.0"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "tag", "v2.0.0"],
            cwd=td, capture_output=True, check=True
        )

        result = get_latest_git_tag(Path(td))
        assert result == "v2.0.0"


def test_get_latest_git_tag_no_tags():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        result = get_latest_git_tag(Path(td))
        assert result is None


def test_find_git_tag_drift_mismatch():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=td, capture_output=True, check=True
        )
        (Path(td) / "test.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "tag", "v2.0.0"],
            cwd=td, capture_output=True, check=True
        )

        docs = {"README.md": "This project uses version 1.0.0"}
        drifts = find_git_tag_drift(Path(td), docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_version"] == "1.0.0"
        assert drifts[0]["git_tag"] == "v2.0.0"


def test_find_git_tag_drift_match():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=td, capture_output=True, check=True
        )
        (Path(td) / "test.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "tag", "v1.0.0"],
            cwd=td, capture_output=True, check=True
        )

        docs = {"README.md": "This project uses version 1.0.0"}
        drifts = find_git_tag_drift(Path(td), docs)
        assert len(drifts) == 0


def test_find_git_tag_drift_no_tag():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        docs = {"README.md": "Version 1.0.0"}
        drifts = find_git_tag_drift(Path(td), docs)
        assert len(drifts) == 0


def test_git_tag_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init"], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=td, capture_output=True, check=True
        )
        (Path(td) / "test.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=td, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=td, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "tag", "v2.0.0"],
            cwd=td, capture_output=True, check=True
        )
        (Path(td) / "README.md").write_text("Uses version 1.0.0")

        from driftcheck.detector import scan_repo
        result = scan_repo(Path(td))
        assert "git_tag_drifts" in result
        assert len(result["git_tag_drifts"]) == 1
