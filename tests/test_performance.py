"""Performance benchmark test for parallel file I/O.

This test verifies that parallel file reading produces correct results
for large repos with many files. It's a smoke test — real benchmarking
requires timeit and is run separately.
"""
from pathlib import Path
import tempfile

from driftcheck.detector import _read_files_parallel, scan_repo


def test_parallel_read_matches_sequential(tmp_path):
    """Parallel reading produces the same content as sequential."""
    # Create multiple files
    files = {
        "file1.txt": "Content of file 1",
        "file2.txt": "Content of file 2",
        "file3.txt": "Content of file 3",
        "file4.txt": "Content of file 4",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    
    # Read in parallel
    result = _read_files_parallel(tmp_path, ["file1.txt", "file2.txt", "file3.txt", "file4.txt"])
    
    # All contents should be present (order may vary due to parallel execution)
    for content in files.values():
        assert content in result


def test_parallel_read_empty_patterns(tmp_path):
    """Empty patterns list returns empty string."""
    (tmp_path / "test.txt").write_text("test")
    assert _read_files_parallel(tmp_path, []) == ""


def test_parallel_read_no_matches(tmp_path):
    """Non-matching patterns return empty string."""
    (tmp_path / "test.txt").write_text("test")
    assert _read_files_parallel(tmp_path, ["nonexistent.*"]) == ""


def test_parallel_read_glob_pattern(tmp_path):
    """Glob patterns work correctly."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.rs").write_text("fn a() {}")
    (tmp_path / "src" / "b.rs").write_text("fn b() {}")
    
    result = _read_files_parallel(tmp_path, ["src/*.rs"])
    assert "fn a()" in result
    assert "fn b()" in result


def test_scan_repo_with_many_files():
    """scan_repo completes successfully with many files (parallel I/O exercised)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Create many files to exercise parallel I/O
        (root / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (root / "README.md").write_text("Rust 1.96.1 project")
        (root / "Dockerfile").write_text("FROM rust:1.96.1")
        (root / "docker-compose.yml").write_text("image: rust:1.96.1")
        (root / ".gitattributes").write_text("* text=auto eol=lf\n")
        
        # Create extra toolchain files to trigger parallel path
        (root / "versions.tf").write_text('terraform { required_providers { aws = { source = "hashicorp/aws" version = "5.0.0" } } }')
        (root / ".circleci").mkdir()
        (root / ".circleci" / "config.yml").write_text("image: cimg/rust:1.96")
        (root / ".gitlab-ci.yml").write_text("image: rust:1.96.1")
        (root / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"\nrust-version = "1.96.1"')
        
        result = scan_repo(root)
        assert result["toolchain_version"] == "1.96.1"
        assert result["drifts"] == []  # no drift
        assert "dart_drifts" in result
