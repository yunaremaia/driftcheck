"""Tests for requirements.txt vs pyproject.toml PEP 621 drift."""
from pathlib import Path

from driftcheck.detectors.python_req import (
    find_python_req_drift,
    parse_pyproject_dependencies,
    parse_requirements,
    specs_conflict,
)


PYPROJECT = """
[project]
name = "demo"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.28.0,<3.0.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
"""


def test_parse_pep621_arrays():
    required, optional, found = parse_pyproject_dependencies(PYPROJECT)
    assert found
    assert required["requests"].startswith(">=")
    assert "pydantic" in required
    assert "pytest" in optional
    assert "pytest" not in required


def test_parse_inline_dependencies():
    text = '[project]\ndependencies = ["flask>=2.0"]\n'
    required, _, found = parse_pyproject_dependencies(text)
    assert found
    assert "flask" in required


def test_major_pin_outside_range_is_drift():
    req = "requests==2.31.0\npydantic==1.10.13\n"
    drifts = find_python_req_drift(req, PYPROJECT)
    packages = {d["package"] for d in drifts}
    assert "pydantic" in packages
    assert "requests" not in packages


def test_compatible_pin_is_quiet():
    req = "requests==2.31.0\npydantic==2.5.0\n"
    drifts = find_python_req_drift(req, PYPROJECT)
    assert drifts == []


def test_missing_from_each_side():
    req = "requests==2.31.0\norphan==1.0\n"
    text = """
[project]
dependencies = [
    "requests>=2.28",
    "httpx>=0.27",
]
"""
    drifts = find_python_req_drift(req, text)
    details = " ".join(d["detail"] for d in drifts)
    assert "orphan" in details
    assert "httpx" in details


def test_optional_extra_not_required_in_requirements():
    req = "requests==2.31.0\npydantic==2.1.0\n"
    assert find_python_req_drift(req, PYPROJECT) == []


def test_poetry_project_without_pep621_is_ignored():
    req = "requests==1.0\n"
    text = '[tool.poetry.dependencies]\nrequests = "^2.0"\n'
    assert find_python_req_drift(req, text) == []


def test_requirement_include(tmp_path: Path):
    (tmp_path / "constraints.txt").write_text("pydantic==1.10.0\n", encoding="utf-8")
    req = "-r constraints.txt\nrequests==2.31.0\n"
    drifts = find_python_req_drift(req, PYPROJECT, root=tmp_path)
    assert any(d["package"] == "pydantic" for d in drifts)


def test_name_normalization():
    pkgs = parse_requirements("Some_Package==1.2.3\n")
    assert "some-package" in pkgs


def test_specs_conflict_same_major_ranges():
    assert not specs_conflict(">=2.28", ">=2.31,<3")
    assert specs_conflict(">=1.0", ">=2.0")


def test_scan_repo_python_req(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["pydantic>=2.0"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("pydantic==1.10.13\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["package"] == "pydantic" for item in result["python_req_drifts"])
