"""Tests for Maven drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.maven import (
    parse_maven_java_version,
    find_maven_drift,
)


class TestParseMavenJavaVersion:
    def test_java_version(self):
        pom = '<project><java.version>17</java.version></project>'
        assert parse_maven_java_version(pom) == "17"

    def test_maven_compiler_source(self):
        pom = '<project><maven.compiler.source>11</maven.compiler.source></project>'
        assert parse_maven_java_version(pom) == "11"

    def test_empty(self):
        assert parse_maven_java_version("") is None



    def test_decimal_version(self):
        pom = '<project><java.version>1.8</java.version></project>'
        assert parse_maven_java_version(pom) == "1.8"



    def test_maven_compiler_target(self):
        pom = '<project><maven.compiler.target>11</maven.compiler.target></project>'
        assert parse_maven_java_version(pom) == "11"



    def test_no_version(self):
        pom = '<project><modelVersion>4.0.0</modelVersion></project>'
        assert parse_maven_java_version(pom) is None



    def test_release_tag(self):
        pom = '<project><maven.compiler.release>17</maven.compiler.release></project>'
        assert parse_maven_java_version(pom) == "17"


class TestFindMavenDrift:
    def test_drift_detected(self):
        pom = '<project><java.version>17</java.version></project>'
        docs = {"README.md": "Requires Java 11"}
        result = find_maven_drift(pom, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "11"
        assert result[0]["maven_version"] == "17"

    def test_no_drift(self):
        pom = '<project><java.version>17</java.version></project>'
        docs = {"README.md": "Requires Java 17"}
        assert find_maven_drift(pom, docs) == []


    def test_detects_drift_major(self):
        pom = '<project><java.version>17</java.version></project>'
        docs = {"README.md": "Requires Java 11"}
        result = find_maven_drift(pom, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "11"
        assert result[0]["maven_version"] == "17"



    def test_drift_same_major_different_minor_ignored(self):
        pom = '<project><java.version>17.0</java.version></project>'
        docs = {"README.md": "Java 17.1"}
        assert find_maven_drift(pom, docs) == []



    def test_missing_docs_returns_empty(self):
        pom = '<project><java.version>17</java.version></project>'
        assert find_maven_drift(pom, {}) == []


# ---- Terraform ----


    def test_missing_pom_returns_empty(self):
        assert find_maven_drift("", {"README.md": "Java 17"}) == []



    def test_multiple_docs(self):
        pom = '<project><java.version>17</java.version></project>'
        docs = {
            "README.md": "Java 17 required",
            "CONTRIBUTING.md": "Build with Java 11",
        }
        result = find_maven_drift(pom, docs)
        assert len(result) == 1
        assert result[0]["file"] == "CONTRIBUTING.md"


