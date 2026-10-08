"""Tests for the Poetry pyproject.toml drift detector."""

from driftcheck.detectors.poetry import (
    parse_poetry_pyproject,
    find_poetry_drift,
    POETRY_PYTHON_RE,
    POETRY_PKG_RE,
    _major_minor,
)


class TestParsePoetryPyproject:
    """Tests for parse_poetry_pyproject."""

    def test_empty_string(self):
        assert parse_poetry_pyproject("") == {}

    def test_no_poetry_section(self):
        text = "[project]\ndependencies = []"
        assert parse_poetry_pyproject(text) == {}

    def test_python_version(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        result = parse_poetry_pyproject(text)
        assert result["python"] == "3.12"

    def test_multiple_packages(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
requests = "^2.28"
numpy = "^1.24"
pandas = ">=2.0"
"""
        result = parse_poetry_pyproject(text)
        assert result["python"] == "3.12"
        assert result["requests"] == "2.28"
        assert result["numpy"] == "1.24"
        assert result["pandas"] == "2.0"

    def test_dev_dependencies(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"

[tool.poetry.dev-dependencies]
pytest = "^7.0"
black = "^23.0"
"""
        result = parse_poetry_pyproject(text)
        assert result["python"] == "3.12"
        assert result["pytest"] == "7.0"
        assert result["black"] == "23.0"

    def test_project_dependencies(self):
        text = """
[project.dependencies]
requests = ">=2.28"
"""
        result = parse_poetry_pyproject(text)
        assert result["requests"] == "2.28"

    def test_skips_non_package_keys(self):
        text = """
[tool.poetry]
name = "my-package"

[tool.poetry.dependencies]
python = "^3.12"
requests = "^2.28"
"""
        result = parse_poetry_pyproject(text)
        assert "name" not in result
        assert result["python"] == "3.12"
        assert result["requests"] == "2.28"

    def test_case_insensitive_section_matching(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        result = parse_poetry_pyproject(text)
        assert "python" in result


class TestFindPoetryDrift:
    """Tests for find_poetry_drift."""

    def test_empty_pyproject(self):
        assert find_poetry_drift("", {}) == []

    def test_no_poetry_section(self):
        text = "[project]\ndependencies = []"
        docs = {"README.md": "Python 3.12"}
        assert find_poetry_drift(text, docs) == []

    def test_python_drift_detected(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        docs = {"README.md": "Python 3.11"}
        drifts = find_poetry_drift(text, docs)
        assert len(drifts) >= 1
        python_drifts = [d for d in drifts if d["package"] == "python"]
        assert len(python_drifts) == 1
        assert python_drifts[0]["doc_version"] == "3.11"
        assert python_drifts[0]["pyproject_version"] == "3.12"

    def test_python_no_drift(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        docs = {"README.md": "Python 3.12"}
        drifts = find_poetry_drift(text, docs)
        python_drifts = [d for d in drifts if d["package"] == "python"]
        assert len(python_drifts) == 0

    def test_package_drift_detected(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
numpy = "^1.26"
"""
        docs = {"README.md": "numpy 1.24"}
        drifts = find_poetry_drift(text, docs)
        numpy_drifts = [d for d in drifts if d["package"] == "numpy"]
        assert len(numpy_drifts) == 1
        assert numpy_drifts[0]["doc_version"] == "1.24"
        assert numpy_drifts[0]["pyproject_version"] == "1.26"

    def test_package_no_drift(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
numpy = "^1.26"
"""
        docs = {"README.md": "numpy 1.26"}
        drifts = find_poetry_drift(text, docs)
        numpy_drifts = [d for d in drifts if d["package"] == "numpy"]
        assert len(numpy_drifts) == 0

    def test_multiple_drifts(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
numpy = "^1.26"
requests = "^2.31"
"""
        docs = {"README.md": "Python 3.11 numpy 1.24 requests 2.31"}
        drifts = find_poetry_drift(text, docs)
        packages = {d["package"] for d in drifts}
        assert "python" in packages
        assert "numpy" in packages
        assert "requests" not in packages  # no drift for requests

    def test_no_docs(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        assert find_poetry_drift(text, {}) == []

    def test_major_minor_comparison(self):
        """Test that 3.12 and 3.12.1 are considered same version."""
        text = """
[tool.poetry.dependencies]
python = "^3.12.1"
"""
        docs = {"README.md": "Python 3.12"}
        drifts = find_poetry_drift(text, docs)
        python_drifts = [d for d in drifts if d["package"] == "python"]
        assert len(python_drifts) == 0  # same major.minor

    def test_drift_across_multiple_docs(self):
        text = """
[tool.poetry.dependencies]
python = "^3.12"
"""
        docs = {
            "README.md": "Python 3.12",
            "CONTRIBUTING.md": "Python 3.11",
        }
        drifts = find_poetry_drift(text, docs)
        contrib_drifts = [d for d in drifts if d["file"] == "CONTRIBUTING.md"]
        assert len(contrib_drifts) == 1
        assert contrib_drifts[0]["package"] == "python"


class TestMajorMinor:
    """Tests for _major_minor helper."""

    def test_simple_version(self):
        assert _major_minor("1.2") == ("1", "2")

    def test_three_part_version(self):
        assert _major_minor("1.2.3") == ("1", "2")

    def test_single_part_version(self):
        assert _major_minor("3") == ("3", "0")


class TestRegexPatterns:
    """Tests for the regex patterns."""

    def test_poetry_python_re(self):
        assert POETRY_PYTHON_RE.match('python = "^3.12"')
        assert POETRY_PYTHON_RE.match('python = ">=3.11"')
        assert POETRY_PYTHON_RE.match('python = "~3.10"')

    def test_poetry_pkg_re(self):
        assert POETRY_PKG_RE.match('requests = "^2.28"')
        assert POETRY_PKG_RE.match('numpy = ">=1.24"')
        assert POETRY_PKG_RE.match('pandas = "~2.0"')
