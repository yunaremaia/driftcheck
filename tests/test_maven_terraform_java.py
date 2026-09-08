"""Tests for Maven, Terraform, and Java/Gradle drift detectors."""
from __future__ import annotations
import pytest

from driftcheck.detectors.maven import (
    parse_maven_java_version,
    find_maven_drift,
)
from driftcheck.detectors.terraform import (
    parse_terraform_provider_versions,
    find_terraform_drift,
)
from driftcheck.detectors.java import (
    parse_gradle_java_version,
    find_java_drift,
)


# ---- Maven ----

class TestParseMavenJavaVersion:
    def test_java_version(self):
        pom = '<project><java.version>17</java.version></project>'
        assert parse_maven_java_version(pom) == "17"

    def test_maven_compiler_source(self):
        pom = '<project><maven.compiler.source>11</maven.compiler.source></project>'
        assert parse_maven_java_version(pom) == "11"

    def test_maven_compiler_target(self):
        pom = '<project><maven.compiler.target>11</maven.compiler.target></project>'
        assert parse_maven_java_version(pom) == "11"

    def test_release_tag(self):
        pom = '<project><maven.compiler.release>17</maven.compiler.release></project>'
        assert parse_maven_java_version(pom) == "17"

    def test_decimal_version(self):
        pom = '<project><java.version>1.8</java.version></project>'
        assert parse_maven_java_version(pom) == "1.8"

    def test_no_version(self):
        pom = '<project><modelVersion>4.0.0</modelVersion></project>'
        assert parse_maven_java_version(pom) is None

    def test_empty(self):
        assert parse_maven_java_version("") is None


class TestFindMavenDrift:
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

    def test_multiple_docs(self):
        pom = '<project><java.version>17</java.version></project>'
        docs = {
            "README.md": "Java 17 required",
            "CONTRIBUTING.md": "Build with Java 11",
        }
        result = find_maven_drift(pom, docs)
        assert len(result) == 1
        assert result[0]["file"] == "CONTRIBUTING.md"

    def test_missing_pom_returns_empty(self):
        assert find_maven_drift("", {"README.md": "Java 17"}) == []

    def test_missing_docs_returns_empty(self):
        pom = '<project><java.version>17</java.version></project>'
        assert find_maven_drift(pom, {}) == []


# ---- Terraform ----

class TestParseTerraformProviderVersions:
    def test_single_provider(self):
        tf = 'terraform { required_providers { aws = { source = "hashicorp/aws" version = "5.0.0" } } }'
        result = parse_terraform_provider_versions(tf)
        assert result == {"hashicorp/aws": "5.0.0"}

    def test_multiple_providers(self):
        tf = (
            'terraform { required_providers { '
            'aws = { source = "hashicorp/aws" version = "5.0.0" } '
            'azurerm = { source = "hashicorp/azurerm" version = "3.0.0" }'
            ' } }'
        )
        result = parse_terraform_provider_versions(tf)
        assert result["hashicorp/aws"] == "5.0.0"
        assert result["hashicorp/azurerm"] == "3.0.0"

    def test_empty(self):
        assert parse_terraform_provider_versions("") == {}

    def test_no_required_providers(self):
        tf = 'resource "aws_instance" "foo" { }'
        assert parse_terraform_provider_versions(tf) == {}


class TestFindTerraformDrift:
    def test_no_drift(self):
        tf = {"versions.tf": 'terraform { required_providers { aws = { source = "hashicorp/aws" version = "5.0.0" } } }'}
        docs = {"README.md": "Provider hashicorp/aws v5.0.0"}
        assert find_terraform_drift(tf, docs) == []

    def test_empty_terraform_files(self):
        assert find_terraform_drift({}, {"README.md": "Terraform 1.5"}) == []

    def test_empty_docs(self):
        tf = {"versions.tf": 'terraform { required_providers { aws = { source = "hashicorp/aws" version = "5.0.0" } } }'}
        assert find_terraform_drift(tf, {}) == []


# ---- Java/Gradle ----

class TestParseGradleJavaVersion:
    def test_source_compatibility_numeric(self):
        gradle = 'sourceCompatibility = "17"'
        assert parse_gradle_java_version(gradle) == "17"

    def test_source_compatibility_dot_separator(self):
        gradle = "sourceCompatibility = '11'"
        assert parse_gradle_java_version(gradle) == "11"

    def test_jvm_target(self):
        gradle = 'jvmTarget = "17"'
        assert parse_gradle_java_version(gradle) == "17"

    def test_java_version_constant(self):
        gradle = "sourceCompatibility = JavaVersion.VERSION_17"
        assert parse_gradle_java_version(gradle) == "17"

    def test_java_version_constant_old(self):
        gradle = "sourceCompatibility = JavaVersion.VERSION_11"
        assert parse_gradle_java_version(gradle) == "11"

    def test_no_version(self):
        gradle = 'plugins { id("java") }'
        assert parse_gradle_java_version(gradle) is None

    def test_empty(self):
        assert parse_gradle_java_version("") is None


class TestFindJavaDrift:
    def test_no_drift(self):
        gradle = 'sourceCompatibility = "17"'
        docs = {"README.md": "Requires Java 17"}
        assert find_java_drift(gradle, docs) == []

    def test_detects_drift(self):
        gradle = 'sourceCompatibility = "17"'
        docs = {"README.md": "Requires Java 11"}
        result = find_java_drift(gradle, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "11"
        assert result[0]["gradle_version"] == "17"

    def test_missing_gradle_returns_empty(self):
        assert find_java_drift("", {"README.md": "Java 17"}) == []

    def test_missing_docs_returns_empty(self):
        gradle = 'sourceCompatibility = "17"'
        assert find_java_drift(gradle, {}) == []

    def test_kotlin_jvm_target_drift(self):
        gradle = 'jvmTarget = "17"'
        docs = {"README.md": "Kotlin targets JVM 11"}
        result = find_java_drift(gradle, docs)
        assert len(result) == 1
