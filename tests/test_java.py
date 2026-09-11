"""Tests for Java (Gradle) drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.java import (
    parse_gradle_java_version,
    find_java_drift,
)


class TestParseGradleJavaVersion:
    def test_source_compatibility(self):
        text = "sourceCompatibility = '17'"
        assert parse_gradle_java_version(text) == "17"

    def test_jvm_target(self):
        text = 'jvmTarget = "11"'
        assert parse_gradle_java_version(text) == "11"

    def test_empty(self):
        assert parse_gradle_java_version("") is None


class TestFindJavaDrift:
    def test_drift_detected(self):
        gradle = "sourceCompatibility = '17'"
        docs = {"README.md": "Requires Java 11"}
        result = find_java_drift(gradle, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "11"
        assert result[0]["gradle_version"] == "17"

    def test_no_drift(self):
        gradle = "sourceCompatibility = '17'"
        docs = {"README.md": "Requires Java 17"}
        assert find_java_drift(gradle, docs) == []

    def test_empty_gradle(self):
        assert find_java_drift("", {"README.md": "Java 17"}) == []
