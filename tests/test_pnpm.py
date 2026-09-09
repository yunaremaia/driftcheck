"""Tests for pnpm workspace drift detection."""
import pytest
from driftcheck.detectors.pnpm import (
    parse_pnpm_workspace,
    find_pnpm_workspace_drift,
    _extract_package_json_workspaces,
)


def test_parse_pnpm_workspace_basic():
    text = "packages:\n  - 'packages/*'\n  - 'apps/*'\n"
    assert parse_pnpm_workspace(text) == ["packages/*", "apps/*"]


def test_parse_pnpm_workspace_with_comments():
    text = "# Workspace config\npackages:\n  - 'packages/*'\n  - '!**/test/**'\n"
    assert parse_pnpm_workspace(text) == ["packages/*", "!**/test/**"]


def test_parse_pnpm_workspace_empty():
    assert parse_pnpm_workspace("") is None


def test_parse_pnpm_workspace_no_packages():
    text = "other: value\n"
    assert parse_pnpm_workspace(text) is None


def test_extract_package_json_workspaces_array():
    text = '{"name": "test", "workspaces": ["packages/*", "apps/*"]}'
    assert _extract_package_json_workspaces(text) == ["packages/*", "apps/*"]


def test_extract_package_json_workspaces_packages_field():
    text = '{"name": "test", "workspaces": {"packages": ["packages/*"]}}'
    assert _extract_package_json_workspaces(text) == ["packages/*"]


def test_extract_package_json_workspaces_none():
    text = '{"name": "test"}'
    assert _extract_package_json_workspaces(text) is None


def test_find_pnpm_workspace_drift_no_drift():
    pnpm = "packages:\n  - 'packages/*'\n"
    pkg = '{"workspaces": ["packages/*"]}'
    docs = {"README.md": "monorepo"}
    assert find_pnpm_workspace_drift(pnpm, pkg, docs) == []


def test_find_pnpm_workspace_drift_mismatch():
    pnpm = "packages:\n  - 'packages/*'\n  - 'apps/*'\n"
    pkg = '{"workspaces": ["packages/*"]}'
    docs = {"README.md": "monorepo"}
    drifts = find_pnpm_workspace_drift(pnpm, pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["pnpm_packages"] == ["packages/*", "apps/*"]
    assert drifts[0]["package_json_workspaces"] == ["packages/*"]


def test_find_pnpm_workspace_drift_no_pnpm():
    assert find_pnpm_workspace_drift(None, "{}", {}) == []


def test_find_pnpm_workspace_drift_no_pkg():
    pnpm = "packages:\n  - 'packages/*'\n"
    assert find_pnpm_workspace_drift(pnpm, None, {}) == []
