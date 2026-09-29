"""Tests for pyproject.toml [tool.*] Python target drift."""
from driftcheck.detectors.pyproject_tools import (
    find_pyproject_tool_drift,
    parse_tool_python_versions,
)


ALIGNED = """
[project]
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"

[tool.black]
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
"""

DRIFT = """
[project]
requires-python = ">=3.11"

[tool.ruff]
target-version = "py310"

[tool.mypy]
python_version = "3.10"

[tool.pyright]
pythonVersion = "3.12"
"""


def test_parse_targets():
    versions = parse_tool_python_versions(ALIGNED)
    assert versions == {
        "requires-python": "3.11",
        "ruff": "3.11",
        "black": "3.11",
        "mypy": "3.11",
    }


def test_aligned_tools_are_quiet():
    assert find_pyproject_tool_drift(ALIGNED) == []


def test_tools_below_and_above_floor():
    drifts = find_pyproject_tool_drift(DRIFT)
    tools = {d["tool"] for d in drifts}
    assert tools == {"ruff", "mypy", "pyright"}


def test_tools_compared_when_no_requires_python():
    text = """
[tool.ruff]
target-version = "py311"

[tool.black]
target-version = "py312"
"""
    drifts = find_pyproject_tool_drift(text)
    assert len(drifts) == 1
    assert "3.12" in drifts[0]["detail"]
    assert "3.11" in drifts[0]["detail"]


def test_scan_repo_pyproject_tools(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.11"\n\n[tool.ruff]\ntarget-version = "py310"\n',
        encoding="utf-8",
    )
    result = scan_repo(tmp_path)
    assert any(item["tool"] == "ruff" for item in result["pyproject_tool_drifts"])
