"""Tests for version file drift detection (.ruby-version, .python-version, .node-version, .java-version, .terraform-version)."""
import tempfile
from pathlib import Path
from driftcheck.detectors.version_files import (
    parse_ruby_version,
    parse_python_version,
    parse_node_version,
    parse_java_version,
    parse_terraform_version,
    find_version_file_drift,
)


def test_parse_ruby_version_basic():
    assert parse_ruby_version("3.2.2") == "3.2.2"


def test_parse_ruby_version_with_comment():
    assert parse_ruby_version("3.2.2\n# comment") == "3.2.2"


def test_parse_ruby_version_empty():
    assert parse_ruby_version("") is None


def test_parse_python_version_basic():
    assert parse_python_version("3.11.5") == "3.11.5"


def test_parse_python_version_empty():
    assert parse_python_version("") is None


def test_parse_node_version_basic():
    assert parse_node_version("20.11.0") == "20.11.0"


def test_parse_node_version_empty():
    assert parse_node_version("") is None


def test_parse_java_version_basic():
    assert parse_java_version("17") == "17"


def test_parse_java_version_empty():
    assert parse_java_version("") is None


def test_parse_terraform_version_basic():
    assert parse_terraform_version("1.7.0") == "1.7.0"


def test_parse_terraform_version_empty():
    assert parse_terraform_version("") is None


def test_version_file_no_drift_ruby():
    docs = {"README.md": "Requires Ruby 3.2.2"}
    files = {".ruby-version": "3.2.2"}
    assert find_version_file_drift(files, docs, "Ruby") == []


def test_version_file_detects_drift_ruby():
    docs = {"README.md": "Requires Ruby 3.1.0"}
    files = {".ruby-version": "3.2.2"}
    drifts = find_version_file_drift(files, docs, "Ruby")
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Ruby"
    assert drifts[0]["doc_version"] == "3.1.0"
    assert drifts[0]["version_file"] == "3.2.2"


def test_version_file_detects_drift_python():
    docs = {"README.md": "Requires Python 3.10.0"}
    files = {".python-version": "3.11.5"}
    drifts = find_version_file_drift(files, docs, "Python")
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Python"


def test_version_file_detects_drift_node():
    docs = {"README.md": "Requires Node.js 18.0.0"}
    files = {".node-version": "20.11.0"}
    drifts = find_version_file_drift(files, docs, "Node.js")
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Node.js"


def test_version_file_detects_drift_java():
    docs = {"README.md": "Requires Java 11"}
    files = {".java-version": "17"}
    drifts = find_version_file_drift(files, docs, "Java")
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Java"


def test_version_file_detects_drift_terraform():
    docs = {"README.md": "Requires Terraform 1.6.0"}
    files = {".terraform-version": "1.7.0"}
    drifts = find_version_file_drift(files, docs, "Terraform")
    assert len(drifts) == 1
    assert drifts[0]["tool"] == "Terraform"


def test_version_file_no_file_returns_empty():
    docs = {"README.md": "Requires Ruby 3.2.2"}
    assert find_version_file_drift({}, docs, "Ruby") == []


def test_version_file_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".ruby-version").write_text("3.2.2")
        (root / "README.md").write_text("Requires Ruby 3.1.0")
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "ruby_version_drifts" in result
        assert len(result["ruby_version_drifts"]) == 1


def test_version_file_same_major_minor_no_drift():
    docs = {"README.md": "Ruby 3.2"}
    files = {".ruby-version": "3.2.2"}
    assert find_version_file_drift(files, docs, "Ruby") == []


def test_version_file_major_only_match():
    docs = {"README.md": "Ruby 3"}
    files = {".ruby-version": "3.2.2"}
    assert find_version_file_drift(files, docs, "Ruby") == []
