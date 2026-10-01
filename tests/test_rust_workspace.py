"""Tests for the Rust workspace member version drift detector."""

from pathlib import Path
from driftcheck.detectors.rust_workspace import find_rust_workspace_drift
from driftcheck.cli import DETECTOR_INFO
from driftcheck.config import DRIFT_KEYS
import tempfile
import os


def test_all_members_in_sync():
    """All workspace members at the same version - no drift."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Root Cargo.toml
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "1.2.3"

[workspace]
members = ["crates/*"]
""")
        # Two crates in sync
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "1.2.3"
""")
        (root / "crates" / "crate-b").mkdir(parents=True)
        (root / "crates" / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "1.2.3"
""")

        drifts = find_rust_workspace_drift(root)
        assert drifts == [], f"Expected no drifts, got: {drifts}"


def test_one_member_behind():
    """One member at old version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "1.2.3"

[workspace]
members = ["crates/*"]
""")
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "1.2.3"
""")
        (root / "crates" / "crate-b").mkdir(parents=True)
        (root / "crates" / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "1.2.2"
""")

        drifts = find_rust_workspace_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["file"] == "crates/crate-b/Cargo.toml"
        assert drifts[0]["version"] == "1.2.2"
        assert drifts[0]["expected_version"] == "1.2.3"
        assert drifts[0]["kind"] == "rust_workspace_member_drift"


def test_workspace_package_vs_members_mismatch():
    """[workspace.package] version vs. members mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "2.0.0"

[workspace]
members = ["crates/*"]
""")
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "2.0.0"
""")
        (root / "crates" / "crate-b").mkdir(parents=True)
        (root / "crates" / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "1.9.0"
""")

        drifts = find_rust_workspace_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["file"] == "crates/crate-b/Cargo.toml"
        assert drifts[0]["version"] == "1.9.0"
        assert drifts[0]["expected_version"] == "2.0.0"


def test_non_workspace_single_crate():
    """Single crate (not workspace) must report nothing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[package]
name = "single-crate"
version = "1.0.0"
""")
        (root / "src").mkdir()
        (root / "src" / "lib.rs").write_text("")

        drifts = find_rust_workspace_drift(root)
        assert drifts == []


def test_readme_badge_drift():
    """README badge version differs from Cargo.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "1.2.3"

[workspace]
members = ["crates/*"]
""")
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "1.2.3"
""")
        (root / "README.md").write_text("""\
# My Workspace

[![crates.io](https://img.shields.io/crates/v/crate-a/1.2.2)](https://crates.io/crates/crate-a)
""")

        drifts = find_rust_workspace_drift(root)
        badge_drifts = [d for d in drifts if d["kind"] == "rust_workspace_badge_drift"]
        assert len(badge_drifts) == 1
        assert badge_drifts[0]["version"] == "1.2.2"
        assert badge_drifts[0]["expected_version"] == "1.2.3"


def test_exact_member_path():
    """Members listed as exact paths (not glob)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "1.0.0"

[workspace]
members = ["crate-a", "crate-b"]
""")
        (root / "crate-a").mkdir(parents=True)
        (root / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "1.0.0"
""")
        (root / "crate-b").mkdir(parents=True)
        (root / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "0.9.0"
""")

        drifts = find_rust_workspace_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["file"] == "crate-b/Cargo.toml"
        assert drifts[0]["version"] == "0.9.0"


def test_registered_in_scan_repo():
    """The detector must be reachable through scan_repo, not just importable."""
    from driftcheck.detector import scan_repo

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "3.0.0"

[workspace]
members = ["crates/*"]
""")
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "3.0.0"
""")
        (root / "crates" / "crate-b").mkdir(parents=True)
        (root / "crates" / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "2.9.9"
""")

        result = scan_repo(root)
        assert "rust_workspace_drifts" in result
        drifts = result["rust_workspace_drifts"]
        assert len(drifts) == 1
        assert drifts[0]["file"] == "crates/crate-b/Cargo.toml"
        assert drifts[0]["expected_version"] == "3.0.0"


def test_key_is_a_known_drift_key():
    """--only/--exclude resolve the name, so the key must be registered."""
    assert "rust_workspace_drifts" in DRIFT_KEYS
    assert DETECTOR_INFO["rust_workspace_drifts"][0] == "rust-workspace"


def test_emitted_paths_use_posix_separators():
    """Emitted paths must use `/`, never `\\`.

    The values become SARIF `artifactLocation.uri`, which is a URI and always
    uses forward slashes. `str(Path.relative_to())` yields backslashes on
    Windows, which broke the Windows CI matrix legs.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Cargo.toml").write_text("""\
[workspace.package]
version = "1.2.3"

[workspace]
members = ["crates/*"]
""")
        (root / "crates" / "crate-a").mkdir(parents=True)
        (root / "crates" / "crate-a" / "Cargo.toml").write_text("""\
[package]
name = "crate-a"
version = "1.2.3"
""")
        (root / "crates" / "crate-b").mkdir(parents=True)
        (root / "crates" / "crate-b" / "Cargo.toml").write_text("""\
[package]
name = "crate-b"
version = "1.2.2"
""")
        (root / "crates" / "crate-b" / "README.md").write_text(
            "[![crates.io](https://img.shields.io/crates/v/crate-b/1.0.0)](https://crates.io/crates/crate-b)\n"
        )

        drifts = find_rust_workspace_drift(root)
        assert drifts, "fixture should produce drifts"
        for d in drifts:
            assert "\\" not in d["file"], f"backslash in emitted path: {d['file']!r}"
