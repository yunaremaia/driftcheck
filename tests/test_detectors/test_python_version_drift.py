"""Tests for python_version_drift detector: unified Python version drift detection."""

from pathlib import Path
import tempfile

from driftcheck.detectors.python_version_drift import (
    parse_python_version_file,
    parse_requires_python,
    _normalize,
    _floor_from_sources,
    _python_version_from_workflow,
    find_python_version_drift,
)


class TestNormalize:
    def test_major_minor(self):
        assert _normalize("3.12") == (3, 12, 0)

    def test_major_minor_patch(self):
        assert _normalize("3.12.5") == (3, 12, 5)

    def test_prerelease_stripped(self):
        assert _normalize("3.13.0rc1") == (3, 13, 0)

    def test_major_only(self):
        assert _normalize("3") == (3, 0, 0)

    def test_invalid(self):
        assert _normalize("not-a-version") == (0, 0, 0)


class TestParsePythonVersionFile:
    def test_simple_version(self):
        assert parse_python_version_file("3.12.5") == (3, 12, 5)

    def test_with_comment(self):
        assert parse_python_version_file("3.12.5  # production") == (3, 12, 5)

    def test_with_hash_comment(self):
        assert parse_python_version_file("# production\n3.12.5") == (3, 12, 5)

    def test_major_only(self):
        assert parse_python_version_file("3") == (3, 0, 0)

    def test_prerelease(self):
        assert parse_python_version_file("3.13.0rc1") == (3, 13, 0)

    def test_empty(self):
        assert parse_python_version_file("") is None

    def test_only_comments(self):
        assert parse_python_version_file("# comment\n# another") is None


class TestParseRequiresPython:
    def test_pyproject_floor(self):
        assert parse_requires_python('requires-python = ">=3.10"') == (3, 10, 0)

    def test_pyproject_range(self):
        assert parse_requires_python('requires-python = ">=3.10,<3.13"') == (3, 10, 0)

    def test_setup_cfg(self):
        assert parse_requires_python("python_requires = >=3.8") == (3, 8, 0)

    def test_setup_py(self):
        assert parse_requires_python('python_requires=">=3.9"') == (3, 9, 0)

    def test_poetry_style(self):
        # Poetry uses [tool.poetry.dependencies] python = "^3.10"
        # The core python_version_drift parser focuses on requires-python /
        # python_requires; Poetry style is handled by the separate python.py detector
        assert parse_requires_python('[tool.poetry.dependencies]\npython = "^3.10"') is None

    def test_missing(self):
        assert parse_requires_python("[project]\nname = 'foo'") is None


class TestFloorFromSources:
    def test_pyproject_takes_precedence(self):
        floor, source = _floor_from_sources(
            'requires-python = ">=3.10"',
            "python_requires = >=3.8",
            'python_requires=">=3.9"',
        )
        assert floor == (3, 10, 0)
        assert source == "pyproject.toml"

    def test_setup_cfg_fallback(self):
        floor, source = _floor_from_sources(None, "python_requires = >=3.8", None)
        assert floor == (3, 8, 0)
        assert source == "setup.cfg"

    def test_setup_py_fallback(self):
        floor, source = _floor_from_sources(None, None, 'python_requires=">=3.9"')
        assert floor == (3, 9, 0)
        assert source == "setup.py"

    def test_no_floor(self):
        floor, source = _floor_from_sources(None, None, None)
        assert floor is None
        assert source is None


class TestPythonVersionFromWorkflow:
    def test_basic(self):
        text = """
- uses: actions/setup-python@v5
  with:
    python-version: '3.10'
"""
        assert _python_version_from_workflow(text) == (3, 10, 0)

    def test_double_quoted(self):
        text = """
- uses: actions/setup-python@v4
  with:
    python-version: "3.11"
"""
        assert _python_version_from_workflow(text) == (3, 11, 0)

    def test_no_version_input(self):
        text = """
- uses: actions/setup-python@v5
  with:
    cache: 'pip'
"""
        assert _python_version_from_workflow(text) is None

    def test_multiple_steps_first_match(self):
        text = """
- uses: actions/setup-python@v4
  with:
    python-version: '3.9'
- uses: actions/setup-python@v5
  with:
    python-version: '3.10'
"""
        assert _python_version_from_workflow(text) == (3, 9, 0)


class TestFindPythonVersionDrift:
    def _make_root(self, files: dict[str, str | None]) -> Path:
        """Create a temporary directory with the given files."""
        tmp = tempfile.mkdtemp()
        root = Path(tmp)
        for relpath, content in files.items():
            fpath = root / relpath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            if content is not None:
                fpath.write_text(content, encoding="utf-8")
        return root

    def test_no_drift_when_no_floor(self, tmp_path):
        """No floor means no drift detectable."""
        result = find_python_version_drift(
            tmp_path, None, None, None, {}
        )
        assert result == []

    def test_workflow_path_uses_posix_separators(self, windows_path, tmp_path):
        """Emitted `file` must use `/`, never `\\`.

        The value is reported verbatim in JSON/Markdown output and compared
        against `--file` filters and baseline entries, so a backslash
        separator breaks all three.
        """
        root = windows_path(tmp_path)
        wf_dir = root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("""
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
""")

        result = find_python_version_drift(
            root, 'requires-python = ">=3.10"', None, None, {}
        )
        workflows = [d for d in result if d["type"] == "workflow"]
        assert len(workflows) == 1, f"expected a workflow drift, got: {result}"
        assert workflows[0]["file"] == ".github/workflows/ci.yml"
        assert "\\" not in workflows[0]["file"]

    def test_no_drift_when_versions_match(self, tmp_path):
        """Python version in workflow matches pyproject requires-python."""
        root = self._make_root({
            "pyproject.toml": 'requires-python = ">=3.10"',
            ".github/workflows/ci.yml": """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/setup-python@v5
      with:
        python-version: '3.10'
""",
        })
        result = find_python_version_drift(root, "requires-python = \">=3.10\"", None, None, {})
        assert result == []

    def test_workflow_version_below_floor(self, tmp_path):
        """setup-python action uses Python version below pyproject requires-python."""
        root = self._make_root({
            "pyproject.toml": 'requires-python = ">=3.10"',
            ".github/workflows/ci.yml": """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
""",
        })
        result = find_python_version_drift(
            root,
            'requires-python = ">=3.10"',
            None,
            None,
            {},
        )
        assert len(result) == 1
        assert result[0]["type"] == "workflow"
        assert result[0]["file"].replace("\\", "/") == ".github/workflows/ci.yml"
        assert result[0]["tool"] == "Python"
        assert result[0]["workflow_version"] == "3.9.0"
        assert result[0]["doc_version"] == "3.9.0"
        assert result[0]["floor_version"] == "3.10.0"
        assert result[0]["floor_source"] == "pyproject.toml"

    def test_python_version_file_below_floor(self, tmp_path):
        """pyenv .python-version pins below pyproject requires-python."""
        root = self._make_root({
            "pyproject.toml": 'requires-python = ">=3.10"',
            ".python-version": "3.9.5",
        })
        result = find_python_version_drift(
            root,
            'requires-python = ">=3.10"',
            None,
            None,
            {},
        )
        assert len(result) == 1
        assert result[0]["type"] == "version_file"
        assert result[0]["file"] == ".python-version"
        assert result[0]["tool"] == "Python"
        assert result[0]["pin_version"] == "3.9.5"
        assert result[0]["doc_version"] == "3.9.5"
        assert result[0]["version_file"] == "3.9.5"
        assert result[0]["floor_version"] == "3.10.0"
        assert result[0]["floor_source"] == "pyproject.toml"

    def test_doc_below_floor(self, tmp_path):
        """README mentions Python 3.8 but pyproject requires >=3.10."""
        root = self._make_root({
            "pyproject.toml": 'requires-python = ">=3.10"',
            "README.md": "# My Project\n\nRequires Python 3.8+",
        })
        result = find_python_version_drift(
            root,
            'requires-python = ">=3.10"',
            None,
            None,
            {"README.md": "Requires Python 3.8+"},
        )
        assert len(result) == 1
        assert result[0]["type"] == "doc"
        assert result[0]["file"] == "README.md"
        assert result[0]["tool"] == "Python"
        assert result[0]["doc_version"] == "3.8"
        assert result[0]["version_file"] == "3.10.0"
        assert result[0]["floor_version"] == "3.10.0"

    def test_setup_cfg_as_floor(self, tmp_path):
        """setup.cfg python_requires is the floor when no pyproject.toml."""
        root = self._make_root({
            "setup.cfg": "[options]\npython_requires = >=3.8",
            ".python-version": "3.7.0",
        })
        result = find_python_version_drift(
            root,
            None,
            "[options]\npython_requires = >=3.8",
            None,
            {},
        )
        assert len(result) == 1
        assert result[0]["floor_source"] == "setup.cfg"
        assert result[0]["floor_version"] == "3.8.0"

    def test_setup_py_as_floor(self, tmp_path):
        """setup.py python_requires is the floor."""
        root = self._make_root({
            "setup.py": 'from setuptools import setup\nsetup(\n    python_requires=">=3.8",\n)',
            ".python-version": "3.7.0",
        })
        result = find_python_version_drift(
            root,
            None,
            None,
            'from setuptools import setup\nsetup(\n    python_requires=">=3.8",\n)',
            {},
        )
        assert len(result) == 1
        assert result[0]["floor_source"] == "setup.py"
        assert result[0]["floor_version"] == "3.8.0"

    def test_combined_drifts(self, tmp_path):
        """Multiple drift sources detected in one call."""
        root = self._make_root({
            "pyproject.toml": 'requires-python = ">=3.10"',
            ".python-version": "3.8",
            ".github/workflows/ci.yml": """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
""",
            "README.md": "# Project\nRequires Python 3.8+",
        })
        result = find_python_version_drift(
            root,
            'requires-python = ">=3.10"',
            None,
            None,
            {"README.md": "# Project\nRequires Python 3.8+"},
        )
        assert len(result) == 3  # version_file + workflow + doc
        types = {d["type"] for d in result}
        assert types == {"version_file", "workflow", "doc"}
