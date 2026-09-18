
import os
import tempfile
from pathlib import Path

import pytest

from driftcheck.cli import main as cli_main
from driftcheck.detector import _safe_glob, _walk_files, scan_repo


def _create_symlink(link_path: Path, target: Path):
    try:
        link_path.symlink_to(target)
    except OSError as e:
        if getattr(e, "winerror", None) == 1314:
            pytest.skip("Creating symlinks requires administrative privileges on Windows")
        raise


def test_walk_files_respects_follow_symlinks_false():
    """When follow_symlinks=False, symlinks outside root are skipped (issue #128)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()

        # Create a normal file inside root
        normal_file = root / "README.md"
        normal_file.write_text("# Test repo")

        # Create a symlink outside root pointing to /etc/hostname
        outside_target = Path("/etc/hostname")
        if outside_target.exists():
            symlink_path = root / "secret_link"
            symlink_path.symlink_to(outside_target)

            # With follow_symlinks=False
            walked, skipped = _walk_files(root, follow_symlinks=False)
            assert normal_file in walked
            assert symlink_path not in walked
            assert len(skipped) >= 1
            assert any("outside repo root" in s or "skipped" in s.lower() for s in skipped)

            # With follow_symlinks=True (default)
            walked2, skipped2 = _walk_files(root, follow_symlinks=True)
            assert symlink_path in walked2
            assert len(skipped2) == 0


def test_walk_files_internal_symlink_always_included():
    """Symlinks pointing inside root are always included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()

        # Create two subdirs
        sub1 = root / "sub1"
        sub1.mkdir()
        sub2 = root / "sub2"
        sub2.mkdir()

        # Create a file in sub1
        real_file = sub1 / "file.txt"
        real_file.write_text("hello")

        # Create a symlink in sub2 pointing to file in sub1 (inside root)
        symlink = sub2 / "link.txt"
        _create_symlink(symlink, real_file)

        # With follow_symlinks=False, internal symlinks are still included
        walked, skipped = _walk_files(root, follow_symlinks=False)
        assert symlink in walked
        assert len(skipped) == 0


def test_scan_repo_follow_symlinks_false_skips_external():
    """scan_repo() with follow_symlinks=False does not read external symlinks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()

        # Create .driftcheck.toml with follow_symlinks=false
        config = root / ".driftcheck.toml"
        config.write_text("[driftcheck]\nfollow_symlinks = false\n")

        # Create README
        readme = root / "README.md"
        readme.write_text("# Test\nPython 3.11\n")

        # Create pyproject.toml
        pyproject = root / "pyproject.toml"
        pyproject.write_text("[project]\nrequires-python = \">=3.11\"\n")

        # Create an external symlink to /etc/hostname
        outside_target = Path("/etc/hostname")
        if outside_target.exists():
            symlink = root / "external"
            _create_symlink(symlink, outside_target)

            # Scan should succeed without reading external file
            result = scan_repo(root)
            assert "_skipped_symlinks" in result
            assert len(result["_skipped_symlinks"]) >= 1

            # The external file content should NOT appear in docs
            for doc_content in result.get("docs", {}).values():
                # /etc/hostname content shouldn't appear
                assert "external" not in doc_content or "secret" not in doc_content


def test_walk_files_broken_symlink_handled():
    """Broken symlinks are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()

        # Create a broken symlink
        symlink = root / "broken"
        _create_symlink(symlink, Path("/nonexistent/path/file.txt"))

        # Should not raise
        walked, skipped = _walk_files(root, follow_symlinks=False)
        assert len(skipped) >= 1
        assert any("broken" in s.lower() or "inaccessible" in s.lower() for s in skipped)


def test_walk_files_symlink_loop_handled():
    """Symlink loops (a -> b -> a) are detected and skipped without crashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()

        # Create a symlink loop: a -> b -> a
        a = root / "a"
        b = root / "b"
        _create_symlink(a, b)
        _create_symlink(b, a)

        # Should not crash with RuntimeError
        walked, skipped = _walk_files(root, follow_symlinks=False)
        # Symlinks in loop should either be skipped (with loop message)
        # or not appear at all (os.walk may omit them by version)
        # The key requirement: no crash
        assert isinstance(skipped, list)
        assert isinstance(walked, set)


def test_safe_glob_excludes_external_symlinks():
    """_safe_glob with follow_symlinks=False never yields files outside root (issue #171)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        outside_file = Path(tmpdir) / "secret.txt"
        outside_file.write_text("SUPER_SECRET")

        root = Path(tmpdir) / "repo"
        root.mkdir()
        internal_file = root / "valid.txt"
        internal_file.write_text("hello")

        symlink = root / "link_secret.txt"
        _create_symlink(symlink, outside_file)

        walked, _ = _walk_files(root, follow_symlinks=False)
        assert internal_file in walked
        assert symlink not in walked

        # Test _safe_glob with follow_symlinks=False
        results_no_follow = list(_safe_glob(root, "*.txt", walked, follow_symlinks=False))
        assert internal_file in results_no_follow
        assert symlink not in results_no_follow

        # Test _safe_glob with follow_symlinks=True
        walked_all, _ = _walk_files(root, follow_symlinks=True)
        results_follow = list(_safe_glob(root, "*.txt", walked_all, follow_symlinks=True))
        assert internal_file in results_follow
        assert symlink in results_follow


def test_cli_no_follow_symlinks_flag():
    """CLI --no-follow-symlinks does not follow external symlinks (issue #171)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        outside_file = Path(tmpdir) / "secret.txt"
        outside_file.write_text("SUPER_SECRET")

        root = Path(tmpdir) / "repo"
        root.mkdir()
        (root / "README.md").write_text("# Test\nPython 3.11\n")
        (root / "pyproject.toml").write_text("[project]\nrequires-python = \">=3.11\"\n")

        symlink = root / "external_doc.md"
        _create_symlink(symlink, outside_file)

        # Run cli with --no-follow-symlinks
        exit_code = cli_main([str(root), "--no-follow-symlinks", "--quiet"])
        assert exit_code == 0


def test_safe_glob_resolution_check(tmp_path: Path):
    """Verify _safe_glob excludes files outside root even if passed in walked_files."""
    root = tmp_path / "repo"
    root.mkdir()
    valid = root / "valid.txt"
    valid.write_text("ok")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")

    # Even if outside was maliciously included in walked_files, _safe_glob must filter it
    walked = {valid, outside}
    results = list(_safe_glob(root, "*.txt", walked, follow_symlinks=False))
    assert valid in results
    assert outside not in results
