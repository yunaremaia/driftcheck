"""Integration tests for GitHub Actions drift detection."""
from pathlib import Path
from driftcheck.detectors.actions import (
    find_actions_node_drift,
    find_gh_actions_version_drift,
    GH_ACTIONS_LATEST,
)


def _write_workflow(root: Path, name: str, content: str) -> None:
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / name).write_text(content)


class TestActionsNodeDrift:
    def test_detects_deprecated_node20(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
        )
        drifts = find_actions_node_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(d["action"] == "actions/checkout" and d["current"] == "v4" for d in drifts)

    def test_no_drift_on_fixed_version(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v5\n",
        )
        drifts = find_actions_node_drift(tmp_path)
        assert not any(d["action"] == "actions/checkout" for d in drifts)

    def test_no_drift_without_workflows(self, tmp_path):
        drifts = find_actions_node_drift(tmp_path)
        assert drifts == []

    def test_detects_multiple_deprecated(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n",
        )
        drifts = find_actions_node_drift(tmp_path)
        actions = {d["action"] for d in drifts}
        assert "actions/checkout" in actions
        assert "actions/setup-node" in actions


class TestActionsVersionDrift:
    def test_detects_outdated_action(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v3\n",
        )
        drifts = find_gh_actions_version_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(d["action"] == "actions/checkout" and d["current"] == "v3" for d in drifts)

    def test_no_drift_when_up_to_date(self, tmp_path):
        latest = GH_ACTIONS_LATEST["actions/checkout"]
        _write_workflow(
            tmp_path,
            "ci.yml",
            f"jobs:\n  build:\n    steps:\n      - uses: actions/checkout@{latest}\n",
        )
        drifts = find_gh_actions_version_drift(tmp_path)
        assert not any(d["action"] == "actions/checkout" for d in drifts)

    def test_no_drift_without_workflows(self, tmp_path):
        drifts = find_gh_actions_version_drift(tmp_path)
        assert drifts == []

    def test_ignores_unknown_actions(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  build:\n    steps:\n      - uses: some/random-action@v1\n",
        )
        drifts = find_gh_actions_version_drift(tmp_path)
        assert drifts == []

    def test_detects_in_yaml_extension(self, tmp_path):
        _write_workflow(
            tmp_path,
            "ci.yaml",
            "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v2\n",
        )
        drifts = find_gh_actions_version_drift(tmp_path)
        assert any(d["file"] == ".github/workflows/ci.yaml" for d in drifts)
