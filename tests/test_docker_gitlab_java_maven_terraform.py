"""Tests for Docker, GitLab, Java, Maven, and Terraform drift detectors."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.docker import (
    parse_dockerfile_from,
    find_docker_drift,
)
from driftcheck.detectors.gitlab import (
    parse_gitlab_images,
    find_gitlab_drift,
)
from driftcheck.detectors.java import (
    parse_gradle_java_version,
    find_java_drift,
)
from driftcheck.detectors.maven import (
    parse_maven_java_version,
    find_maven_drift,
)
from driftcheck.detectors.terraform import (
    parse_terraform_provider_versions,
    find_terraform_drift,
)


# ---- Docker ----

class TestParseDockerfileImages:
    def test_single_from(self):
        text = "FROM node:20-slim"
        result = parse_dockerfile_from(text)
        assert result == {"node": "20-slim"}

    def test_multiple_from(self):
        text = "FROM node:20-slim\nFROM nginx:1.21"
        result = parse_dockerfile_from(text)
        assert result == {"node": "20-slim", "nginx": "1.21"}

    def test_empty(self):
        assert parse_dockerfile_from("") == {}

    def test_no_from(self):
        text = "RUN echo hello"
        assert parse_dockerfile_from(text) == {}


class TestFindDockerDrift:
    def test_drift_detected(self):
        dockerfiles = {"Dockerfile": "FROM node:20-slim"}
        docs = {"README.md": "Docker node:18"}
        result = find_docker_drift(dockerfiles, docs)
        assert len(result) >= 1

    def test_no_drift(self):
        dockerfiles = {"Dockerfile": "FROM node:20-slim"}
        docs = {"README.md": "Docker node:20"}
        assert find_docker_drift(dockerfiles, docs) == []

    def test_empty_dockerfiles(self):
        assert find_docker_drift({}, {"README.md": "Node 20"}) == []


# ---- GitLab CI ----

class TestParseGitlabCiImages:
    def test_single_image(self):
        text = "image: node:20"
        result = parse_gitlab_images(text)
        assert result == {"node": "20"}

    def test_multiple_images(self):
        text = "image: node:20\njob:\n  image: python:3.11"
        result = parse_gitlab_images(text)
        assert "node" in result or "python" in result

    def test_empty(self):
        assert parse_gitlab_images("") == {}


class TestFindGitlabCiDrift:
    def test_drift_detected(self):
        gitlab = {"gitlab-ci.yml": "image: node:20"}
        docs = {"README.md": "image node:18"}
        result = find_gitlab_drift(gitlab, docs)
        assert len(result) >= 1

    def test_no_drift(self):
        gitlab = {"gitlab-ci.yml": "image: node:20"}
        docs = {"README.md": "image node:20"}
        assert find_gitlab_drift(gitlab, docs) == []


# ---- Java (Gradle) ----

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


# ---- Maven ----

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


# ---- Terraform ----

class TestParseTerraformProviderVersions:
    def test_single_provider(self):
        text = 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'
        result = parse_terraform_provider_versions(text)
        assert result == {"hashicorp/aws": "5.0"}

    def test_multiple_providers(self):
        text = 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n  google = {\n    source  = "hashicorp/google"\n    version = "4.0"\n  }\n}'
        result = parse_terraform_provider_versions(text)
        assert result == {"hashicorp/aws": "5.0", "hashicorp/google": "4.0"}

    def test_empty(self):
        assert parse_terraform_provider_versions("") == {}


class TestFindTerraformDrift:
    def test_drift_detected(self):
        tf = {"main.tf": 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'}
        docs = {"README.md": "provider \"4.0\""}
        result = find_terraform_drift(tf, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "4.0"
        assert result[0]["terraform_version"] == "5.0"

    def test_no_drift(self):
        tf = {"main.tf": 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'}
        docs = {"README.md": "provider \"5.0\""}
        assert find_terraform_drift(tf, docs) == []
