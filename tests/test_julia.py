"""Tests for Julia Project.toml/Manifest.toml drift."""
from driftcheck.detectors.julia import find_julia_drift, parse_manifest_versions, parse_project_compat

PROJECT = """
name = "MyProject"
[deps]
DataFrames = "a93c6f00-e57d-5684-b7b6-d8193f3e46c0"
[compat]
julia = "1.9"
DataFrames = "1.5"
Plots = "1.3"
"""

MANIFEST = """
[[deps.DataFrames]]
uuid = "a93c6f00-e57d-5684-b7b6-d8193f3e46c0"
version = "1.5.2"
"""


def test_parse_compat_skips_julia_and_uuids():
    pins = parse_project_compat(PROJECT)
    assert pins == {"DataFrames": "1.5", "Plots": "1.3"}
    assert "julia" not in pins


def test_parse_manifest():
    assert parse_manifest_versions(MANIFEST)["DataFrames"] == "1.5.2"


def test_readme_major_minor_drift():
    docs = {"README.md": "Uses DataFrames.jl v1.6 and Plots.jl v1.3.\n"}
    drifts = find_julia_drift(PROJECT, "", docs)
    assert [item["package"] for item in drifts] == ["DataFrames"]


def test_manifest_version_overrides_compat():
    docs = {"README.md": "DataFrames.jl v1.5\n"}
    assert find_julia_drift(PROJECT, MANIFEST, docs) == []


def test_aligned_readme_is_quiet():
    docs = {"README.md": "DataFrames.jl v1.5.1 and Plots v1.3.2\n"}
    assert find_julia_drift(PROJECT, "", docs) == []


def test_scan_repo_julia(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "Project.toml").write_text('[compat]\nDataFrames = "1.5"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("DataFrames.jl v1.6\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["package"] == "DataFrames" for item in result["julia_drifts"])
