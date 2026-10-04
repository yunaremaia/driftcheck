"""Regression tests for issue #467: `--git-mode` never detected any change.

``get_changed_files()`` ran ``git diff --name-only -- <base>`` with the base
commit *after* the ``--`` separator, so git read the base as a pathspec. A
pathspec of ``HEAD~1`` matches no file, the command succeeded with an empty list
on every repository, and every ``--git-mode`` invocation short-circuited to
"no files changed" and exited 0.

The mock-based tests elsewhere in ``test_git_mode.py`` cannot catch this: a
patched ``subprocess.run`` returns whatever the test says regardless of argv.
These tests run real git against a real repository.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest

from driftcheck.git_mode import get_changed_and_untracked, get_changed_files

pytestmark = pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not available",
)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "d@e.x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "d@e.x",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


@pytest.fixture
def repo_with_one_change(tmp_path: Path) -> Path:
    """A repo whose second commit changes Dockerfile and nothing else."""
    _git("init", "-q", "-b", "main", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    _git("add", "-A", cwd=tmp_path)
    _git("commit", "-qm", "base", cwd=tmp_path)
    (tmp_path / "Dockerfile").write_text(
        "FROM node:18.0.0 AS build\nFROM node:20.0.0 AS run\n"
    )
    _git("add", "-A", cwd=tmp_path)
    _git("commit", "-qm", "add conflicting Dockerfile stages", cwd=tmp_path)
    return tmp_path


class TestBaseIsARevisionNotAPathspec:
    def test_detects_the_changed_file(self, repo_with_one_change):
        """The one changed file must be returned, not an empty set."""
        assert get_changed_files(repo_with_one_change, "HEAD~1") == {"Dockerfile"}

    def test_matches_plain_git_diff(self, repo_with_one_change):
        """driftcheck must agree with `git diff --name-only <base> --`."""
        expected = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "--"],
            cwd=repo_with_one_change, capture_output=True, text=True,
        ).stdout.split()
        assert sorted(get_changed_files(repo_with_one_change, "HEAD~1")) == sorted(expected)
        assert expected, "the fixture must produce a non-empty diff"

    def test_and_untracked_also_sees_the_change(self, repo_with_one_change):
        """get_changed_and_untracked() shares the same base helper."""
        assert "Dockerfile" in get_changed_and_untracked(repo_with_one_change, "HEAD~1")

    def test_multiple_commits_back(self, repo_with_one_change):
        """A base several commits back is still a revision, not a pathspec."""
        _git("commit", "-q", "--allow-empty", "-m", "third", cwd=repo_with_one_change)
        assert get_changed_files(repo_with_one_change, "HEAD~2") == {"Dockerfile"}

    def test_no_changes_yields_empty_set(self, repo_with_one_change):
        """A base equal to HEAD legitimately changes nothing."""
        assert get_changed_files(repo_with_one_change, "HEAD") == set()


class TestGitModeExitCode:
    """The reported symptom: --git-mode exits 0 on a tree that fails a full scan."""

    def test_git_mode_fails_where_full_scan_fails(self, repo_with_one_change, capsys):
        from driftcheck.cli import main

        assert main([str(repo_with_one_change)]) == 1, "full scan must fail"
        capsys.readouterr()

        rc = main(["--git-mode", "--git-base", "HEAD~1", str(repo_with_one_change)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "no files changed since" not in out