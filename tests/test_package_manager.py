"""Tests for package manager drift detection."""
import tempfile
from pathlib import Path
from driftcheck.detectors.package_manager import (
    parse_package_manager_field,
    detect_lockfile_manager,
    find_package_manager_drift,
)


def test_parse_package_manager_field_pnpm():
    pkg_json = '{"packageManager": "pnpm@8.0.0"}'
    assert parse_package_manager_field(pkg_json) == "pnpm@8.0.0"


def test_parse_package_manager_field_none():
    pkg_json = '{"name": "test"}'
    assert parse_package_manager_field(pkg_json) is None


def test_detect_lockfile_manager_bun():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "bun.lockb").write_text("")
        assert detect_lockfile_manager(root) == "bun"


def test_detect_lockfile_manager_pnpm():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pnpm-lock.yaml").write_text("")
        assert detect_lockfile_manager(root) == "pnpm"


def test_detect_lockfile_manager_none():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        assert detect_lockfile_manager(root) is None


def test_find_package_manager_drift_mismatch():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg_json = '{"packageManager": "pnpm@8.0.0"}'
        (root / "package-lock.json").write_text("")
        docs = {"README.md": "Use npm for this project"}
        
        drifts = find_package_manager_drift(pkg_json, root, docs)
        assert len(drifts) == 1
        assert drifts[0]["package_manager_field"] == "pnpm"
        assert drifts[0]["actual_manager"] == "npm"


def test_find_package_manager_drift_match():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg_json = '{"packageManager": "pnpm@8.0.0"}'
        (root / "pnpm-lock.yaml").write_text("")
        docs = {"README.md": "Use pnpm"}
        
        drifts = find_package_manager_drift(pkg_json, root, docs)
        assert len(drifts) == 0


def test_find_package_manager_drift_no_field():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg_json = '{"name": "test"}'
        (root / "package-lock.json").write_text("")
        docs = {"README.md": "Some text"}
        
        drifts = find_package_manager_drift(pkg_json, root, docs)
        assert len(drifts) == 0


def test_package_manager_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"packageManager": "yarn@3.0.0"}')
        (root / "bun.lock").write_text("")
        (root / "README.md").write_text("Some docs")
        
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "package_manager_drifts" in result
        assert len(result["package_manager_drifts"]) == 1
