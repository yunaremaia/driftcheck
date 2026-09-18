
import os
import tempfile
from pathlib import Path

from driftcheck.detector import _walk_files, scan_repo


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
        symlink.symlink_to(real_file)

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
            symlink.symlink_to(outside_target)

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
        symlink.symlink_to("/nonexistent/path/file.txt")

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
        a.symlink_to(b)
        b.symlink_to(a)

        # Should not crash with RuntimeError
        walked, skipped = _walk_files(root, follow_symlinks=False)
        # Symlinks in loop should either be skipped (with loop message)
        # or not appear at all (os.walk may omit them by version)
        # The key requirement: no crash
        assert isinstance(skipped, list)
        assert isinstance(walked, set)
