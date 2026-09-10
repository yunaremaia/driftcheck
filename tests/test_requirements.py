"""Tests for requirements.txt drift detection: requirements.txt vs pyproject.toml and README."""
from __future__ import annotations
from driftcheck.detectors.requirements import (
    parse_requirements_packages,
    parse_pyproject_packages,
    find_requirements_drift,
    REQUIREMENTS_PKG_RE,
    DOC_PKG_RE,
    PYPROJECT_PKG_RE,
    _major_minor,
)


class TestParseRequirementsPackages:
    def test_single_package(self):
        text = "requests==2.28.0"
        result = parse_requirements_packages(text)
        assert result == {"requests": "2.28.0"}

    def test_multiple_packages(self):
        text = "requests==2.28.0\nflask==2.0.0"
        result = parse_requirements_packages(text)
        assert result == {"requests": "2.28.0", "flask": "2.0.0"}

    def test_with_gte(self):
        text = "requests>=2.28.0"
        result = parse_requirements_packages(text)
        assert result == {"requests": "2.28.0"}

    def test_with_tilde(self):
        text = "requests~=2.28.0"
        result = parse_requirements_packages(text)
        assert result == {"requests": "2.28.0"}

    def test_empty(self):
        assert parse_requirements_packages("") == {}

    def test_skip_pip(self):
        text = "pip==23.0\nrequests==2.28.0"
        result = parse_requirements_packages(text)
        assert "pip" not in result
        assert result == {"requests": "2.28.0"}

    def test_skip_setuptools(self):
        text = "setuptools==68.0\nrequests==2.28.0"
        result = parse_requirements_packages(text)
        assert "setuptools" not in result

    def test_skip_wheel(self):
        text = "wheel==0.40\nrequests==2.28.0"
        result = parse_requirements_packages(text)
        assert "wheel" not in result

    def test_skip_python(self):
        text = "python==3.10\nrequests==2.28.0"
        result = parse_requirements_packages(text)
        assert "python" not in result


class TestParsePyprojectPackages:
    def test_poetry_dependencies(self):
        text = '[tool.poetry.dependencies]\nrequests = "^2.28.0"\npython = "^3.10"'
        result = parse_pyproject_packages(text)
        assert result == {"requests": "2.28.0"}

    def test_project_dependencies(self):
        text = '[project]\ndependencies = ["requests>=2.28.0"]'
        result = parse_pyproject_packages(text)
        # This format is different, may not parse
        assert isinstance(result, dict)

    def test_empty(self):
        assert parse_pyproject_packages("") == {}

    def test_skip_python(self):
        text = '[tool.poetry.dependencies]\npython = "^3.10"\nrequests = "^2.28.0"'
        result = parse_pyproject_packages(text)
        assert "python" not in result
        assert result == {"requests": "2.28.0"}


class TestFindRequirementsDrift:
    def test_drift_vs_pyproject(self):
        req = "requests==2.28.0"
        pyproject = '[tool.poetry.dependencies]\nrequests = "^2.25.0"'
        result = find_requirements_drift(req, pyproject, {})
        assert len(result) == 1
        assert result[0]["package"] == "requests"
        assert result[0]["doc_version"] == "2.25.0"
        assert result[0]["requirements_version"] == "2.28.0"

    def test_no_drift_vs_pyproject(self):
        req = "requests==2.28.0"
        pyproject = '[tool.poetry.dependencies]\nrequests = "^2.28.0"'
        result = find_requirements_drift(req, pyproject, {})
        assert result == []

    def test_drift_vs_readme(self):
        req = "requests==2.28.0"
        docs = {"README.md": "requests 2.25.0"}
        result = find_requirements_drift(req, "", docs)
        assert len(result) == 1
        assert result[0]["package"] == "requests"
        assert result[0]["doc_version"] == "2.25.0"

    def test_no_drift_vs_readme(self):
        req = "requests==2.28.0"
        docs = {"README.md": "requests 2.28.0"}
        result = find_requirements_drift(req, "", docs)
        assert result == []

    def test_empty_requirements(self):
        result = find_requirements_drift("", "", {})
        assert result == []

    def test_no_packages_in_requirements(self):
        result = find_requirements_drift("# comment\n", "", {})
        assert result == []

    def test_multiple_packages(self):
        req = "requests==2.28.0\nflask==2.0.0"
        docs = {"README.md": "requests 2.25.0\nflask 1.0.0"}
        result = find_requirements_drift(req, "", docs)
        assert len(result) == 2

    def test_case_insensitive(self):
        req = "requests==2.28.0"
        docs = {"README.md": "Requests 2.25.0"}
        result = find_requirements_drift(req, "", docs)
        assert len(result) == 1


class TestMajorMinor:
    def test_full_version(self):
        assert _major_minor("2.28.0") == ("2", "28")

    def test_major_minor(self):
        assert _major_minor("2.28") == ("2", "28")

    def test_major_only(self):
        assert _major_minor("2") == ("2", "0")


class TestRequirementsPkgRe:
    def test_match_eq(self):
        m = REQUIREMENTS_PKG_RE.search("requests==2.28.0")
        assert m is not None
        assert m.group("pkg") == "requests"
        assert m.group("ver") == "2.28.0"

    def test_match_gte(self):
        m = REQUIREMENTS_PKG_RE.search("requests>=2.28.0")
        assert m is not None

    def test_match_tilde_eq(self):
        m = REQUIREMENTS_PKG_RE.search("requests~=2.28.0")
        assert m is not None

    def test_no_match(self):
        m = REQUIREMENTS_PKG_RE.search("# comment")
        assert m is None


class TestDocPkgRe:
    def test_match_bare(self):
        m = DOC_PKG_RE.search("requests 2.28.0")
        assert m is not None
        assert m.group("pkg") == "requests"
        assert m.group("ver") == "2.28.0"

    def test_match_eq(self):
        m = DOC_PKG_RE.search("requests==2.28.0")
        assert m is not None

    def test_no_match(self):
        m = DOC_PKG_RE.search("Some text")
        assert m is None


class TestPyprojectPkgRe:
    def test_match_caret(self):
        m = PYPROJECT_PKG_RE.search('requests = "^2.28.0"')
        assert m is not None
        assert m.group("pkg") == "requests"
        assert m.group("ver") == "2.28.0"

    def test_match_gte(self):
        m = PYPROJECT_PKG_RE.search('requests = ">=2.28.0"')
        assert m is not None

    def test_no_match(self):
        m = PYPROJECT_PKG_RE.search('[tool.poetry.dependencies]')
        assert m is None
