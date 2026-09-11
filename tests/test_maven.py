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
