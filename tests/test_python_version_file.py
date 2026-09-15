"""Tests for Python version pins against project requirements."""

import json

import pytest

from driftcheck.cli import main
from driftcheck.detector import scan_repo
from driftcheck.detectors.python_version import find_python_version_file_drift
from driftcheck.git_mode import DETECTOR_FILE_PATTERNS, filter_detectors_by_files


@pytest.mark.parametrize(
    ("pin", "requirement", "expected"),
    [
        ("3.9", ">=3.10", True),
        ("3.10", ">=3.10", False),
        ("3.11.2", ">=3.10", False),
        ("3.9.18", "<3.13,>=3.10", True),
        ("3.10", ">=3.9,>=3.11", True),
        ("3.9", "~=3.10", True),
        ("3.9", "==3.10.*", True),
        ("3.11", "<3.10", False),
        ("3.11", "!=3.11", False),
        ("3.10.1", ">=3.10.2", True),
        ("3.10.2", ">=3.10.2", False),
        ("3.10", ">=3.10.2", False),
        ("3", ">=3.10", False),
        ("2", ">=3.10", True),
        ("4", ">=3.10", False),
        ("3.13.0rc1", ">=3.13", False),
        ("3.13.0b1", ">=3.14", True),
        ("3.10.0", ">3.10", True),
        ("3.10.1", ">3.10", False),
        ("3", ">3.10", False),
    ],
)
def test_pin_against_minimum(pin, requirement, expected):
    pyproject = f'[project]\nrequires-python = "{requirement}"\n'
    result = find_python_version_file_drift(pin, pyproject)
    assert bool(result) is expected
    assert not any(d.get("informational") for d in result)


def test_comments_and_single_quoted_requirement():
    result = find_python_version_file_drift(
        "# local interpreter\n\n  3.9.18  # pinned\n",
        "[project] # metadata\nrequires-python = '>=3.10' # minimum\n",
    )
    assert result[0]["doc_version"] == "3.9.18"


@pytest.mark.parametrize(
    "pin", ["", "# comment", "system", "3.12garbage", "3.10\n3.11"]
)
def test_unsupported_pin(pin):
    result = find_python_version_file_drift(
        pin, '[project]\nrequires-python = ">=3.10"'
    )
    assert len(result) == 1
    assert result[0]["informational"] is True


def test_missing_file_or_requirement():
    assert (
        find_python_version_file_drift(None, '[project]\nrequires-python = ">=3.10"')
        == []
    )
    assert find_python_version_file_drift("3.9", '[project]\nname = "example"') == []
    assert find_python_version_file_drift("system", "") == []


@pytest.mark.parametrize(
    "pyproject",
    [
        "",
        '[project]\nname = "example"',
        '[tool.example]\nrequires-python = ">=3.8"',
        '[project]\nname = "example"\n[[tool.example]]\nrequires-python = ">=3.8"',
    ],
)
def test_setup_cfg_fallback(pyproject):
    result = find_python_version_file_drift(
        "3.9", pyproject, "[options]\npython_requires = >=3.10 # minimum\n"
    )
    assert result[0]["source_file"] == "setup.cfg"
    assert result[0]["required_version"] == "3.10"


def test_pyproject_takes_precedence():
    assert (
        find_python_version_file_drift(
            "3.9",
            '[project]\nrequires-python = ">=3.8"',
            "[options]\npython_requires = >=3.10",
        )
        == []
    )


def test_malformed_setup_cfg():
    assert find_python_version_file_drift("3.9", "", "not valid ini") == []


@pytest.mark.parametrize(
    "changed_file", [".python-version", "pyproject.toml", "setup.cfg"]
)
def test_git_mode_inputs(changed_file):
    selected = filter_detectors_by_files({changed_file}, DETECTOR_FILE_PATTERNS)
    assert "python_version_file_drifts" in selected
    assert "python_version_parse_drifts" in selected


def test_scan_python_version_below_floor(tmp_path):
    (tmp_path / ".python-version").write_text("3.9\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )

    result = scan_repo(tmp_path)

    assert len(result.get("python_version_file_drifts", [])) == 1
    drift = result["python_version_file_drifts"][0]
    assert drift["file"] == ".python-version"
    assert drift["doc_version"] == "3.9"
    assert drift["required_version"] == "3.10"
    assert drift["source_file"] == "pyproject.toml"


def test_cli_python_version_below_floor(tmp_path, capsys):
    (tmp_path / ".python-version").write_text("3.9\n", encoding="utf-8")
    (tmp_path / "setup.cfg").write_text(
        "[options]\npython_requires = >=3.10\n", encoding="utf-8"
    )

    assert main([str(tmp_path), "--only", "python_version_file_drifts", "--json"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["python_version_file_drifts"][0]["source_file"] == "setup.cfg"


def test_invalid_python_version_is_informational(tmp_path, capsys):
    (tmp_path / ".python-version").write_text("system\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )

    assert main([str(tmp_path), "--only", "python_version_parse_drifts", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output.get("python_version_parse_drifts", [])) == 1


@pytest.mark.parametrize("pin, expected_rc", [("3.9", 1), ("system", 0)])
@pytest.mark.parametrize("output_format", ["", "--csv", "--sarif", "--report"])
def test_cli_output_formats(tmp_path, capsys, pin, expected_rc, output_format):
    (tmp_path / ".python-version").write_text(pin, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    args = [
        str(tmp_path),
        "--only",
        "python_version_file_drifts,python_version_parse_drifts",
    ]
    if output_format:
        args.append(output_format)
    assert main(args) == expected_rc
    output = capsys.readouterr().out
    assert ".python-version" in output
    if output_format == "--sarif":
        entries = json.loads(output)["runs"][0]["results"]
        assert entries[0]["level"] == ("error" if expected_rc else "warning")
    elif output_format == "--csv":
        assert ("blocking" if expected_rc else "informational") in output
    else:
        assert (
            "below the required minimum" if expected_rc else "Cannot compare"
        ) in output


def test_exclude_python_version_detector(tmp_path):
    (tmp_path / ".python-version").write_text("3.9", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )
    result = scan_repo(tmp_path, enabled_detectors={"python_drifts"})
    assert "python_version_file_drifts" not in result
    assert "python_version_parse_drifts" not in result
