"""Integration tests for Python drift detection."""
from driftcheck.detectors.python import (
    parse_python_version_from_pyproject,
    find_python_drift,
)


class TestParsePythonVersion:
    def test_pyproject(self):
        assert parse_python_version_from_pyproject(
            '[project]\nrequires-python = ">=3.11.0"'
        ) == "3.11"

    def test_pyproject_range(self):
        assert parse_python_version_from_pyproject(
            '[project]\nrequires-python = ">=3.10,<3.13"'
        ) == "3.10"

    def test_missing(self):
        assert parse_python_version_from_pyproject('[project]\nname = "test"') is None


class TestFindPythonDrift:
    def test_drift_detected(self):
        pyproject = '[project]\nrequires-python = ">=3.11"'
        docs = {"README.md": "Built with Python 3.10"}
        drifts = find_python_drift(pyproject, docs)
        assert len(drifts) >= 1
        assert drifts[0]["doc_version"] == "3.10"

    def test_no_drift(self):
        pyproject = '[project]\nrequires-python = ">=3.11"'
        docs = {"README.md": "Built with Python 3.11"}
        drifts = find_python_drift(pyproject, docs)
        assert drifts == []

    def test_no_python_in_docs(self):
        pyproject = '[project]\nrequires-python = ">=3.11"'
        docs = {"README.md": "No python mention here"}
        drifts = find_python_drift(pyproject, docs)
        assert drifts == []

    def test_floor_semantics(self):
        # requires-python is a floor; doc mentioning 3.12 when floor is 3.11 is fine
        pyproject = '[project]\nrequires-python = ">=3.11"'
        docs = {"README.md": "Tested with Python 3.12"}
        drifts = find_python_drift(pyproject, docs)
        assert drifts == []
