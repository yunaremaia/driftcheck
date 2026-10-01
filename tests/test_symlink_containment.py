"""The follow_symlinks policy must actually hold (issue #128 follow-up).

`_walk_files` is the only place that classifies symlinks as inside/outside the
repo root, and `scan_repo` reads root-level config files (pyproject.toml,
README.md, package.json, ...) directly instead of through the walked set. Both
paths must refuse a symlink whose resolved target escapes the repo root.
"""

import os
import tempfile
from pathlib import Path

from driftcheck.detector import _walk_files, scan_repo


def _make_repo(tmpdir):
    """Create root/<name> plus an escaping sibling <name>-secrets/ outside it."""
    base = Path(tmpdir)
    root = base / "repo"
    root.mkdir()
    outside = base / "repo-secrets"
    outside.mkdir()
    (outside / "outside.md").write_text(
        "# Outside\nRequires Python 3.9\nAPI_KEY=sk-LIVE-OUTSIDE-REPO\n"
    )
    (outside / "pyproject.toml").write_text(
        '[project]\nname = "leaked"\nrequires-python = ">=3.9"\n'
    )
    return root, outside


def test_walk_files_rejects_sibling_directory_sharing_prefix():
    """A sibling dir named `repo-secrets` is NOT inside `repo`.

    String-prefix containment ("/…/repo-secrets/…" startswith "/…/repo")
    wrongly accepts it; containment must compare path components.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root, outside = _make_repo(tmpdir)
        link = root / "leaked.md"
        link.symlink_to(outside / "outside.md")

        walked, skipped = _walk_files(root, follow_symlinks=False)

        assert link not in walked, "symlink escaping into a prefix-sharing sibling was followed"
        assert any("leaked.md" in s for s in skipped), f"escape not reported: {skipped}"


def test_scan_repo_ignores_symlinked_root_config_file():
    """A symlinked pyproject.toml must not be read when follow_symlinks=false."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root, outside = _make_repo(tmpdir)
        (root / ".driftcheck.toml").write_text("[driftcheck]\nfollow_symlinks = false\n")
        (root / "README.md").write_text("Requires Python 3.11\n")
        os.symlink(outside / "pyproject.toml", root / "pyproject.toml")

        result = scan_repo(root)

        assert result.get("pyproject_python") is None, (
            "content of a symlink escaping the repo root was parsed as project metadata"
        )
        assert result.get("python_drifts") == []


def test_scan_repo_ignores_symlinked_doc_file():
    """A symlinked README.md must not feed detectors when follow_symlinks=false."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root, outside = _make_repo(tmpdir)
        (root / ".driftcheck.toml").write_text("[driftcheck]\nfollow_symlinks = false\n")
        (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.13"\n')
        os.symlink(outside / "outside.md", root / "README.md")

        result = scan_repo(root)

        assert result.get("python_drifts") == [], (
            "a doc file symlinked outside the repo root was still used as a doc source"
        )
        assert any("README.md" in s for s in result.get("_skipped_symlinks", [])), (
            f"skipped symlink not reported to SARIF: {result.get('_skipped_symlinks')}"
        )


def test_scan_repo_still_reads_real_root_config():
    """Regression guard: genuine in-repo files are still read."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root, _ = _make_repo(tmpdir)
        (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.13"\n')
        (root / "README.md").write_text("Requires Python 3.11\n")

        result = scan_repo(root)

        assert result.get("pyproject_python") == "3.13"
        assert len(result.get("python_drifts", [])) == 1


def test_scan_repo_follows_symlinks_when_policy_enabled():
    """Regression guard: default follow_symlinks=true keeps working."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root, outside = _make_repo(tmpdir)
        (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.13"\n')
        os.symlink(outside / "pyproject.toml", root / "linked.toml")
        (root / "README.md").write_text("Requires Python 3.11\n")

        result = scan_repo(root)

        # linked.toml is not a candidate file, but the policy must not error out
        # and the real pyproject.toml must still be read.
        assert result.get("pyproject_python") == "3.13"
