"""Tests for Scala/SBT version drift."""
from driftcheck.detectors.scala import find_scala_drift, parse_sbt

SBT = """
scalaVersion := "2.13.12"
libraryDependencies += "org.apache.spark" %% "spark-core" % "3.5.0"
"""


def test_parse_sbt():
    scala, deps = parse_sbt(SBT)
    assert scala == "2.13.12"
    assert deps["spark-core"] == "3.5.0"


def test_readme_drift():
    docs = {"README.md": "Built with Scala 2.12 and spark-core 3.4.\n"}
    drifts = find_scala_drift(SBT, docs)
    tools = {item["tool"] for item in drifts}
    assert tools == {"Scala", "spark-core"}


def test_aligned_readme_is_quiet():
    docs = {"README.md": "Requires Scala 2.13.14 and spark-core 3.5.1.\n"}
    assert find_scala_drift(SBT, docs) == []


def test_empty_build():
    assert find_scala_drift("", {"README.md": "Scala 2.13"}) == []


def test_scan_repo_scala(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "build.sbt").write_text('scalaVersion := "2.13.12"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("Requires Scala 2.12.\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["tool"] == "Scala" for item in result["scala_drifts"])
