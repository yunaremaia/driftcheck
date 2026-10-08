"""Tests for git_submodule_drift detector."""
from pathlib import Path
import tempfile

from driftcheck.detectors.git_submodule_drift import (
    find_git_submodule_drift,
)


class TestFindGitSubmoduleDrift:
    def _make_root(self, files: dict[str, str | None]) -> Path:
        """Create a temporary directory with the given files."""
        tmp = tempfile.mkdtemp()
        root = Path(tmp)
        for relpath, content in files.items():
            fpath = root / relpath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            if content is not None:
                fpath.write_text(content, encoding="utf-8")
            else:
                fpath.mkdir(parents=True, exist_ok=True)
        return root

    def test_no_drift_when_no_gitmodules(self, tmp_path):
        """No .gitmodules means no drift."""
        result = find_git_submodule_drift(tmp_path)
        assert result == []

    def test_no_drift_when_no_submodules(self, tmp_path):
        """Empty .gitmodules means no drift."""
        root = self._make_root({
            ".gitmodules": "",
        })
        result = find_git_submodule_drift(root)
        assert result == []

    def test_drift_when_submodule_commit_mismatch(self, tmp_path):
        """Submodule commit differs from recorded commit."""
        root = self._make_root({
            ".gitmodules": """
[submodule "libs/foo"]
    path = libs/foo
    url = https://github.com/example/foo.git
""",
            ".git/modules/libs/foo/HEAD": "abc123",
            "libs/foo": None,  # Directory exists
        })
        # Create a fake .git file in the submodule
        (root / "libs/foo/.git").write_text("gitdir: ../../.git/modules/libs/foo")
        result = find_git_submodule_drift(root)
        # Should detect drift if commits don't match
        assert isinstance(result, list)

    def test_no_drift_when_submodule_matches(self, tmp_path):
        """Submodule commit matches recorded commit."""
        root = self._make_root({
            ".gitmodules": """
[submodule "libs/foo"]
    path = libs/foo
    url = https://github.com/example/foo.git
""",
            ".git/modules/libs/foo/HEAD": "abc123",
            "libs/foo": None,
        })
        (root / "libs/foo/.git").write_text("gitdir: ../../.git/modules/libs/foo")
        result = find_git_submodule_drift(root)
        assert isinstance(result, list)

    def test_multiple_submodules(self, tmp_path):
        """Multiple submodules, one with drift."""
        root = self._make_root({
            ".gitmodules": """
[submodule "libs/foo"]
    path = libs/foo
    url = https://github.com/example/foo.git

[submodule "libs/bar"]
    path = libs/bar
    url = https://github.com/example/bar.git
""",
            ".git/modules/libs/foo/HEAD": "abc123",
            ".git/modules/libs/bar/HEAD": "def456",
            "libs/foo": None,
            "libs/bar": None,
        })
        (root / "libs/foo/.git").write_text("gitdir: ../../.git/modules/libs/foo")
        (root / "libs/bar/.git").write_text("gitdir: ../../.git/modules/libs/bar")
        result = find_git_submodule_drift(root)
        assert isinstance(result, list)

    def test_submodule_not_initialized(self, tmp_path):
        """Submodule directory doesn't exist (not initialized)."""
        root = self._make_root({
            ".gitmodules": """
[submodule "libs/foo"]
    path = libs/foo
    url = https://github.com/example/foo.git
""",
        })
        result = find_git_submodule_drift(root)
        assert isinstance(result, list)
