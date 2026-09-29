"""Tests for Helm Chart.yaml dependency constraints vs Chart.lock."""
from driftcheck.detectors.helm_deps import find_helm_dependency_drift

CHART = """
apiVersion: v2
name: demo
dependencies:
  - name: postgresql
    version: "12.x.x"
    repository: "https://charts.bitnami.com/bitnami"
  - name: redis
    version: "17.0.0"
    repository: "https://charts.bitnami.com/bitnami"
"""

LOCK = """
dependencies:
- name: postgresql
  version: 12.5.0
- name: redis
  version: 18.0.0
"""


def test_wildcard_ok_and_exact_mismatch():
    drifts = find_helm_dependency_drift(CHART, LOCK)
    assert len(drifts) == 1
    assert drifts[0]["package"] == "redis"
    assert drifts[0]["lock_version"] == "18.0.0"


def test_missing_lock_entry():
    lock = "dependencies:\n- name: postgresql\n  version: 12.5.0\n"
    drifts = find_helm_dependency_drift(CHART, lock)
    assert any(item["package"] == "redis" and "missing" in item["detail"] for item in drifts)


def test_absent_lock_file_is_quiet():
    assert find_helm_dependency_drift(CHART, "") == []


def test_aligned_lock_is_quiet():
    lock = LOCK.replace("18.0.0", "17.0.0")
    assert find_helm_dependency_drift(CHART, lock) == []


def test_scan_repo_helm_dependency(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "Chart.yaml").write_text('dependencies:\n- name: redis\n  version: "17.0.0"\n', encoding="utf-8")
    (tmp_path / "Chart.lock").write_text("dependencies:\n- name: redis\n  version: 18.0.0\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["package"] == "redis" for item in result["helm_dependency_drifts"])
