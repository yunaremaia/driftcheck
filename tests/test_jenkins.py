"""Tests for Jenkins drift detection."""
import tempfile
from pathlib import Path
from driftcheck.detectors.jenkins import (
    parse_jenkins_node_agent,
    parse_jenkins_nodejs_version,
    parse_jenkins_python_version,
    parse_jenkins_docker_images,
    find_jenkins_drift,
)


def test_parse_jenkins_node_agent_basic():
    jenkinsfile = "node('linux-agent') { }"
    assert parse_jenkins_node_agent(jenkinsfile) == "linux-agent"


def test_parse_jenkins_node_agent_missing():
    assert parse_jenkins_node_agent("echo 'hello'") is None


def test_parse_jenkins_nodejs_version_basic():
    jenkinsfile = "nodejs '20.11.0' { sh 'npm install' }"
    assert parse_jenkins_nodejs_version(jenkinsfile) == "20.11.0"


def test_parse_jenkins_nodejs_version_missing():
    assert parse_jenkins_nodejs_version("echo 'hello'") is None


def test_parse_jenkins_python_version_basic():
    jenkinsfile = "python '3.11' { sh 'pip install -r requirements.txt' }"
    assert parse_jenkins_python_version(jenkinsfile) == "3.11"


def test_parse_jenkins_python_version_missing():
    assert parse_jenkins_python_version("echo 'hello'") is None


def test_parse_jenkins_docker_images():
    jenkinsfile = "docker.image('node:20-alpine') { }"
    result = parse_jenkins_docker_images(jenkinsfile)
    assert result == {"node": "20-alpine"}


def test_parse_jenkins_docker_images_missing():
    assert parse_jenkins_docker_images("echo 'hello'") == {}


def test_jenkins_no_drift_nodejs():
    jenkinsfile = "nodejs '20.11.0' { sh 'npm install' }"
    docs = {"README.md": "Requires Node.js 20.11.0"}
    assert find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs) == []


def test_jenkins_detects_drift_nodejs():
    jenkinsfile = "nodejs '20.11.0' { sh 'npm install' }"
    docs = {"README.md": "Requires Node.js 18.17.0"}
    drifts = find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs)
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Node.js"
    assert drifts[0]["doc_version"] == "18.17.0"
    assert drifts[0]["jenkins_version"] == "20.11.0"


def test_jenkins_detects_drift_python():
    jenkinsfile = "python '3.11' { sh 'pip install -r requirements.txt' }"
    docs = {"README.md": "Requires Python 3.10"}
    drifts = find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs)
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Python"
    assert drifts[0]["doc_version"] == "3.10"
    assert drifts[0]["jenkins_version"] == "3.11"


def test_jenkins_detects_drift_docker():
    jenkinsfile = "docker.image('node:20-alpine') { }"
    docs = {"README.md": "Uses node:18-alpine"}
    drifts = find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs)
    assert len(drifts) == 1
    assert "Docker" in drifts[0]["tool"]
    assert drifts[0]["doc_version"] == "18"
    assert drifts[0]["jenkins_version"] == "20-alpine"


def test_jenkins_no_jenkinsfile_returns_empty():
    assert find_jenkins_drift({}, {"README.md": "Node 20"}) == []


def test_jenkins_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Jenkinsfile").write_text("nodejs '20.11.0' { sh 'npm install' }")
        (root / "README.md").write_text("Requires Node.js 18.17.0")
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "jenkins_drifts" in result
        assert len(result["jenkins_drifts"]) == 1


def test_jenkins_same_major_minor_no_drift():
    jenkinsfile = "nodejs '20.11.0' { sh 'npm install' }"
    docs = {"README.md": "Requires Node.js 20.11"}
    assert find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs) == []


def test_jenkins_major_only_match():
    jenkinsfile = "nodejs '20.11.0' { sh 'npm install' }"
    docs = {"README.md": "Requires Node.js 20"}
    assert find_jenkins_drift({"Jenkinsfile": jenkinsfile}, docs) == []
