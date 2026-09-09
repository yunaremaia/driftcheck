"""Tests for CI OS drift detection: deprecated GitHub Actions runners."""
from pathlib import Path
import tempfile

from driftcheck.detectors.ci_os import (
    find_ci_os_drift,
    CI_OS_DEPRECATED,
    CI_OS_RE,
)


class TestFindCiOsDrift:
    def test_no_workflows_dir(self, tmp_path):
        assert find_ci_os_drift(tmp_path) == []

    def test_empty_workflows_dir(self, tmp_path):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        assert find_ci_os_drift(tmp_path) == []

    def test_deprecated_ubuntu_2004(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\njobs:\n  build:\n    runs-on: ubuntu-20.04\n"
        )
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["runner"] == "ubuntu-20.04"
        assert drifts[0]["suggested"] == "ubuntu-22.04"

    def test_deprecated_macos_11(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "jobs:\n  test:\n    runs-on: macos-11\n"
        )
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["runner"] == "macos-11"
        assert drifts[0]["suggested"] == "macos-13"

    def test_deprecated_windows_2019(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "jobs:\n  build:\n    runs-on: windows-2019\n"
        )
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1
        assert drifts[0]["runner"] == "windows-2019"

    def test_no_deprecated_runners(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "jobs:\n  build:\n    runs-on: ubuntu-22.04\n"
        )
        assert find_ci_os_drift(tmp_path) == []

    def test_multiple_deprecated_in_same_file(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "jobs:\n  build:\n    runs-on: ubuntu-18.04\n  test:\n    runs-on: macos-10.15\n"
        )
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 2
        runners = {d["runner"] for d in drifts}
        assert "ubuntu-18.04" in runners
        assert "macos-10.15" in runners

    def test_multiple_workflow_files(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("jobs:\n  build:\n    runs-on: ubuntu-20.04\n")
        (wf_dir / "deploy.yml").write_text("jobs:\n  deploy:\n    runs-on: windows-2016\n")
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 2

    def test_yaml_extension(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yaml").write_text("jobs:\n  build:\n    runs-on: ubuntu-20.04\n")
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1

    def test_case_insensitive_runs_on(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("jobs:\n  build:\n    Runs-On: ubuntu-20.04\n")
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1

    def test_all_deprecated_runners_covered(self):
        """Verify all deprecated runners are in the mapping."""
        expected = {"ubuntu-18.04", "ubuntu-20.04", "macos-10.15", "macos-11", "windows-2016", "windows-2019"}
        assert set(CI_OS_DEPRECATED.keys()) == expected

    def test_deprecated_runner_with_comments(self, tmp_path):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "jobs:\n  build:\n    runs-on: ubuntu-20.04  # old runner\n"
        )
        drifts = find_ci_os_drift(tmp_path)
        assert len(drifts) == 1
