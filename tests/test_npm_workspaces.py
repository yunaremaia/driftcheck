"""Tests for npm workspace dependency range drift."""
import json
from pathlib import Path

from driftcheck.detectors.npm_workspaces import find_npm_workspace_drift


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_conflicting_ranges(tmp_path: Path):
    _write(tmp_path / "package.json", {
        "workspaces": ["packages/*"],
        "devDependencies": {"lodash": "^4.17.20"},
    })
    _write(tmp_path / "packages" / "frontend" / "package.json", {
        "dependencies": {"lodash": "^4.17.21", "react": "^18.2.0"},
    })
    _write(tmp_path / "packages" / "backend" / "package.json", {
        "dependencies": {"lodash": "^4.17.19", "express": "^4.18.2"},
    })
    drifts = find_npm_workspace_drift(tmp_path)
    assert len(drifts) == 1
    assert drifts[0]["package"] == "lodash"


def test_aligned_ranges_are_quiet(tmp_path: Path):
    _write(tmp_path / "package.json", {"workspaces": ["packages/*"]})
    _write(tmp_path / "packages" / "a" / "package.json", {
        "dependencies": {"react": "^18.2.0"},
    })
    _write(tmp_path / "packages" / "b" / "package.json", {
        "dependencies": {"react": "^18.2.0"},
    })
    assert find_npm_workspace_drift(tmp_path) == []


def test_pnpm_workspace_yaml(tmp_path: Path):
    _write(tmp_path / "package.json", {})
    (tmp_path / "pnpm-workspace.yaml").write_text(
        "packages:\n  - 'packages/*'\n",
        encoding="utf-8",
    )
    _write(tmp_path / "packages" / "a" / "package.json", {
        "dependencies": {"left-pad": "1.0.0"},
    })
    _write(tmp_path / "packages" / "b" / "package.json", {
        "dependencies": {"left-pad": "1.1.0"},
    })
    drifts = find_npm_workspace_drift(tmp_path)
    assert [d["package"] for d in drifts] == ["left-pad"]


def test_not_a_workspace(tmp_path: Path):
    _write(tmp_path / "package.json", {"dependencies": {"react": "^18.0.0"}})
    assert find_npm_workspace_drift(tmp_path) == []


def test_scan_repo_npm_workspace(tmp_path):
    from driftcheck.detector import scan_repo

    _write(tmp_path / "package.json", {"workspaces": ["packages/*"]})
    _write(tmp_path / "packages" / "a" / "package.json", {"dependencies": {"lodash": "^4.17.21"}})
    _write(tmp_path / "packages" / "b" / "package.json", {"dependencies": {"lodash": "^4.17.19"}})
    result = scan_repo(tmp_path)
    assert any(item["package"] == "lodash" for item in result["npm_workspace_drifts"])
