"""Tests for R DESCRIPTION and renv.lock drift."""
from driftcheck.detectors.r_lang import find_r_drift, parse_description_deps, parse_renv_lock

DESCRIPTION = """
Package: MyAnalysis
Depends: R (>= 4.1)
Imports:
    dplyr (>= 1.0.0),
    ggplot2 (>= 3.4.0)
Suggests:
    knitr
"""

RENV = """
{
  "Packages": {
    "dplyr": {"Package": "dplyr", "Version": "1.0.10"},
    "ggplot2": {"Package": "ggplot2", "Version": "3.4.2"}
  }
}
"""


def test_parse_description_skips_r_and_unversioned():
    deps = parse_description_deps(DESCRIPTION)
    assert deps["dplyr"] == "1.0.0"
    assert deps["ggplot2"] == "3.4.0"
    assert "R" not in deps
    assert "knitr" not in deps


def test_parse_renv():
    assert parse_renv_lock(RENV)["dplyr"] == "1.0.10"


def test_readme_drift_against_description():
    docs = {"README.md": "Requires dplyr 1.1.0 and ggplot2 3.4.\n"}
    drifts = find_r_drift(DESCRIPTION, "", docs)
    assert [item["package"] for item in drifts] == ["dplyr"]


def test_lock_overrides_description():
    docs = {"README.md": "Uses dplyr 1.0.4\n"}
    assert find_r_drift(DESCRIPTION, RENV, docs) == []


def test_invalid_lock_is_ignored():
    assert parse_renv_lock("{") == {}


def test_scan_repo_r(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "DESCRIPTION").write_text("Imports:\n    dplyr (>= 1.0.0)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Requires dplyr 1.1\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["package"] == "dplyr" for item in result["r_drifts"])
