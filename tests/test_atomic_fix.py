"""Tests for atomic write behavior in driftcheck --fix."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from driftcheck.detectors.fix import _atomic_write, apply_fixes


class TestAtomicWrite:
    """Tests for _atomic_write() crash-safety and backup behavior."""

    def test_basic_write(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("original")
        _atomic_write(target, "modified")
        assert target.read_text(encoding="utf-8") == "modified"

    def test_atomic_rename_not_partial(self, tmp_path: Path) -> None:
        """If the process is killed mid-write, original file must be intact."""
        target = tmp_path / "important.txt"
        target.write_text("CRITICAL DATA")

        # Simulate crash during os.replace by making it raise
        with pytest.raises(RuntimeError, match="simulated crash"):
            with patch("driftcheck.detectors.fix.os.replace", side_effect=RuntimeError("simulated crash")):
                _atomic_write(target, "new content")

        # Original file must be untouched
        assert target.read_text(encoding="utf-8") == "CRITICAL DATA"

        # Temp file should be cleaned up
        tmp_files = list(tmp_path.glob("*.driftcheck-tmp"))
        assert len(tmp_files) == 0

    def test_backup_created(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("original")
        backup_dir = tmp_path / "backups"
        _atomic_write(target, "modified", backup_dir=backup_dir)
        assert target.read_text(encoding="utf-8") == "modified"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("test.txt.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "original"

    def test_no_backup_when_disabled(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("original")
        _atomic_write(target, "modified", backup_dir=None)
        assert target.read_text(encoding="utf-8") == "modified"
        assert not (tmp_path / ".driftcheck-backups").exists()

    def test_new_file_no_backup(self, tmp_path: Path) -> None:
        """If file doesn't exist yet, no backup should be created."""
        target = tmp_path / "new.txt"
        backup_dir = tmp_path / "backups"
        _atomic_write(target, "content", backup_dir=backup_dir)
        assert target.read_text(encoding="utf-8") == "content"
        assert not backup_dir.exists()


class TestApplyFixestAtomic:
    """Tests that apply_fixes passes backup flag correctly."""

    def test_fix_creates_backup_by_default(self, tmp_path: Path) -> None:
        """Verify --fix creates .driftcheck-backups/ directory."""
        # Create a drift scenario
        readme = tmp_path / "README.md"
        # DOC_RE expects "Rust" (capital) + whitespace + version
        readme.write_text("Rust 1.93.0\nsetup uses Rust 1.93.0")

        result = {
            "rust_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.93.0",
                    "toolchain_version": "1.96.1",
                }
            ]
        }

        fixed = apply_fixes(tmp_path, result, backup=True)
        assert fixed == ["README.md"]
        assert (tmp_path / ".driftcheck-backups").exists()
        backups = list((tmp_path / ".driftcheck-backups").glob("README.md.*"))
        assert len(backups) == 1

    def test_fix_no_backup_flag(self, tmp_path: Path) -> None:
        """Verify --no-backup skips backup creation."""
        readme = tmp_path / "README.md"
        readme.write_text("Rust 1.93.0")

        result = {
            "rust_drifts": [
                {
                    "file": "README.md",
                    "doc_version": "1.93.0",
                    "toolchain_version": "1.96.1",
                }
            ]
        }

        fixed = apply_fixes(tmp_path, result, backup=False)
        assert fixed == ["README.md"]
        assert not (tmp_path / ".driftcheck-backups").exists()
