"""Tests for Kotlin drift detection (kotlin.py)."""
import pytest

from driftcheck.detectors.kotlin import (
    KOTLIN_PLUGIN_RE,
    KOTLIN_VERSION_RE,
    KOTLIN_DOC_RE,
    parse_kotlin_version,
    find_kotlin_drift,
)


class TestKotlinPluginRegex:
    """Test the Kotlin plugin regex patterns."""

    def test_kotlin_jvm_plugin(self):
        text = 'kotlin("jvm") version "1.9.0"'
        m = KOTLIN_PLUGIN_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_kotlin_plugin_spring(self):
        text = 'kotlin("plugin.spring") version "1.9.22"'
        m = KOTLIN_PLUGIN_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.22"

    def test_kotlin_plugin_serialization(self):
        text = 'kotlin("plugin.serialization") version "1.9.0"'
        m = KOTLIN_PLUGIN_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_id_org_jetbrains_kotlin_jvm(self):
        text = 'id("org.jetbrains.kotlin.jvm") version "1.9.0"'
        m = KOTLIN_PLUGIN_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_id_org_jetbrains_kotlin_android(self):
        text = 'id("org.jetbrains.kotlin.android") version "1.9.0"'
        m = KOTLIN_PLUGIN_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_fallback_any_kotlin_plugin(self):
        text = 'kotlin("allopen") version "1.9.0"'
        m = KOTLIN_VERSION_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_fallback_kapt(self):
        text = 'kotlin("kapt") version "1.9.0"'
        m = KOTLIN_VERSION_RE.search(text)
        assert m is not None
        assert m.group(1) == "1.9.0"

    def test_no_match_non_kotlin(self):
        assert KOTLIN_PLUGIN_RE.search('java("jvm") version "17"') is None


class TestKotlinDocRegex:
    """Test the Kotlin documentation regex."""

    def test_kotlin_version_mention(self):
        m = KOTLIN_DOC_RE.search("Requires Kotlin 1.9 or higher")
        assert m is not None
        assert m.group(1) == "1.9"

    def test_kotlin_v_prefix(self):
        m = KOTLIN_DOC_RE.search("Built with Kotlin v1.9.22")
        assert m is not None
        assert m.group(1) == "1.9.22"

    def test_requires_kotlin(self):
        m = KOTLIN_DOC_RE.search("requires kotlin 1.9")
        assert m is not None
        assert m.group(1) == "1.9"

    def test_no_match(self):
        assert KOTLIN_DOC_RE.search("Just a regular sentence") is None


class TestParseKotlinVersion:
    """Test parse_kotlin_version function."""

    def test_standard_jvm(self):
        assert parse_kotlin_version('kotlin("jvm") version "1.9.0"') == "1.9.0"

    def test_id_format(self):
        assert parse_kotlin_version('id("org.jetbrains.kotlin.jvm") version "1.9.0"') == "1.9.0"

    def test_fallback(self):
        assert parse_kotlin_version('kotlin("allopen") version "1.9.0"') == "1.9.0"

    def test_no_kotlin(self):
        assert parse_kotlin_version('someOtherPlugin version "1.0"') is None

    def test_empty(self):
        assert parse_kotlin_version("") is None


class TestFindKotlinDrift:
    """Test find_kotlin_drift function."""

    def test_detects_drift_major(self):
        gradle = 'kotlin("jvm") version "2.0.0"'
        docs = {"README.md": "This project uses Kotlin 1.9"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_version"] == "1.9"
        assert drifts[0]["gradle_version"] == "2.0.0"

    def test_detects_drift_minor(self):
        gradle = 'kotlin("jvm") version "1.10.0"'
        docs = {"README.md": "Requires Kotlin 1.9"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_version"] == "1.9"
        assert drifts[0]["gradle_version"] == "1.10.0"

    def test_no_drift_same_version(self):
        gradle = 'kotlin("jvm") version "1.9.22"'
        docs = {"README.md": "Uses Kotlin 1.9"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 0

    def test_no_drift_patch_only(self):
        gradle = 'kotlin("jvm") version "1.9.22"'
        docs = {"README.md": "Uses Kotlin 1.9.20"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 0  # patch difference ignored

    def test_no_drift_no_kotlin_in_docs(self):
        gradle = 'kotlin("jvm") version "1.9.0"'
        docs = {"README.md": "Just a regular project"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 0

    def test_no_drift_no_kotlin_in_gradle(self):
        gradle = 'someOtherPlugin version "1.0"'
        docs = {"README.md": "Uses Kotlin 1.9"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 0

    def test_multiple_docs(self):
        gradle = 'kotlin("jvm") version "2.0.0"'
        docs = {
            "README.md": "Uses Kotlin 1.9",
            "CONTRIBUTING.md": "Kotlin 1.8 required",
        }
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 2

    def test_one_drift_per_file(self):
        gradle = 'kotlin("jvm") version "2.0.0"'
        docs = {"README.md": "Kotlin 1.9 and Kotlin 1.8"}
        drifts = find_kotlin_drift(gradle, docs)
        assert len(drifts) == 1

    def test_empty_docs(self):
        gradle = 'kotlin("jvm") version "1.9.0"'
        drifts = find_kotlin_drift(gradle, {})
        assert len(drifts) == 0
