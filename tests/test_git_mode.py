"""Tests for git-mode scanning."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from driftcheck.git_mode import (
    get_changed_files,
    get_changed_and_untracked,
    filter_detectors_by_files,
    _glob_match,
    DETECTOR_FILE_PATTERNS,
)


class TestGetChangedFiles:
    def test_returns_set_on_success(self):
        """Returns set of changed files on successful git diff."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "README.md\nsrc/main.rs\n"
        with patch("subprocess.run", return_value=mock_result):
            result = get_changed_files(Path("/tmp"))
        assert result == {"README.md", "src/main.rs"}

    def test_returns_empty_set_on_failure(self):
        """Returns empty set when git command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        with patch("subprocess.run", return_value=mock_result):
            result = get_changed_files(Path("/tmp"))
        assert result == set()

    def test_returns_empty_set_on_timeout(self):
        """Returns empty set on subprocess timeout."""
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = get_changed_files(Path("/tmp"))
        assert result == set()

    def test_returns_empty_set_on_no_git(self):
        """Returns empty set when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = get_changed_files(Path("/tmp"))
        assert result == set()

    def test_custom_base_commit(self):
        """Uses custom base commit."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\n"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = get_changed_files(Path("/tmp"), "main")
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["git", "diff", "--name-only", "main", "--"]


class TestGetChangedAndUntracked:
    def test_includes_untracked(self):
        """Includes untracked files in addition to changed."""
        mock_diff = MagicMock()
        mock_diff.returncode = 0
        mock_diff.stdout = "README.md\n"
        mock_ls = MagicMock()
        mock_ls.returncode = 0
        mock_ls.stdout = "new_file.py\n"
        with patch("subprocess.run", side_effect=[mock_diff, mock_ls]):
            result = get_changed_and_untracked(Path("/tmp"))
        assert result == {"README.md", "new_file.py"}


class TestGlobMatch:
    def test_exact_match(self):
        assert _glob_match("README.md", "README.md") is True

    def test_no_match(self):
        assert _glob_match("main.rs", "README.md") is False

    def test_star_wildcard(self):
        assert _glob_match("src/main.rs", "*.rs") is True

    def test_double_star_prefix(self):
        assert _glob_match("charts/mychart/values.yaml", "**/values.yaml") is True

    def test_double_star_no_match(self):
        assert _glob_match("README.md", "**/values.yaml") is False


class TestFilterDetectorsByFiles:
    def test_no_changed_files_returns_all(self):
        """If no changed files, all detectors should run."""
        result = filter_detectors_by_files(set(), DETECTOR_FILE_PATTERNS)
        assert result == set(DETECTOR_FILE_PATTERNS.keys())

    def test_readme_change_includes_all_doc_detectors(self):
        """Changing README.md should include all doc-comparing detectors."""
        changed = {"README.md"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        # All doc-comparing detectors should be included
        assert "drifts" in result
        assert "node_drifts" in result
        assert "python_drifts" in result
        assert "go_drifts" in result

    def test_dockerfile_change_includes_docker_detector(self):
        """Changing Dockerfile should include docker_drifts."""
        changed = {"Dockerfile"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        assert "docker_drifts" in result

    def test_src_change_excludes_irrelevant_detectors(self):
        """Changing a source file should exclude most detectors."""
        changed = {"src/main.rs"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        # node_drifts shouldn't run for a Rust source file change
        assert "node_drifts" not in result

    def test_env_file_change_includes_env_detector(self):
        """Changing .env files should include env_drifts."""
        changed = {".env.example"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        assert "env_drifts" in result

    def test_workflow_change_includes_action_detectors(self):
        """Changing workflow files should include action detectors."""
        changed = {".github/workflows/ci.yml"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        assert "actions_drifts" in result
        assert "gh_actions_version_drifts" in result
        assert "ci_os_drifts" in result

    def test_compose_change_includes_env_and_compose(self):
        """Changing compose files should include relevant detectors."""
        changed = {"docker-compose.prod.yml"}
        result = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        assert "env_drifts" in result
        assert "dc_drifts" in result
