"""SARIF output generation for driftcheck.

Converts driftcheck results to SARIF 2.1.0 for ingestion by GitHub Code Scanning,
GitLab Vulnerability Reports, and any other consumer that speaks SARIF.
"""
from __future__ import annotations

from typing import Any

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# Drift type metadata: (rule_id, rule_name, rule_description)
DRIFT_RULES = {
    "drifts": (
        "rust-toolchain-version-drift",
        "Rust Toolchain Version Drift",
        "README documentation references a Rust version that doesn't match rust-toolchain.toml",
    ),
    "rust_drifts": (
        "rust-cargo-version-drift",
        "Rust Cargo Version Drift",
        "README documentation references a Rust version that doesn't match the declared toolchain or Cargo.toml rust-version",
    ),
    "node_drifts": (
        "node-version-drift",
        "Node.js Version Drift",
        "README documentation references a Node.js version that doesn't match package.json engines.node",
    ),
    "bun_drifts": (
        "bun-version-drift",
        "Bun Version Drift",
        "README documentation references a Bun version that doesn't match package.json engines.bun",
    ),
    "python_drifts": (
        "python-version-drift",
        "Python Version Drift",
        "README documentation references a Python version that doesn't match pyproject.toml requires-python",
    ),
    "go_drifts": (
        "go-version-drift",
        "Go Version Drift",
        "README documentation references a Go version that doesn't match go.mod go directive",
    ),
    "docker_drifts": (
        "docker-version-drift",
        "Docker Image Drift",
        "README documentation references a Docker image tag that doesn't match the Dockerfile FROM directive",
    ),
    "docker_multistage_drifts": (
        "docker-multistage-drift",
        "Docker Multi-Stage Drift",
        "Multi-stage Dockerfile uses conflicting tags for the same base image",
    ),
    "docker_bases_drifts": (
        "docker-bases-drift",
        "Docker Base Image Drift",
        "Dockerfile uses a floating/unpinned base image tag or sibling Dockerfiles pin different versions",
    ),
    "java_drifts": (
        "java-gradle-version-drift",
        "Java Gradle Version Drift",
        "README documentation references a Java version that doesn't match build.gradle sourceCompatibility",
    ),
    "maven_drifts": (
        "java-maven-version-drift",
        "Java Maven Version Drift",
        "README documentation references a Java version that doesn't match pom.xml java.version",
    ),
    "terraform_drifts": (
        "terraform-version-drift",
        "Terraform Provider Version Drift",
        "README documentation references a Terraform provider version that doesn't match versions.tf",
    ),
    "circleci_drifts": (
        "circleci-version-drift",
        "CircleCI Image Drift",
        "README documentation references a Docker image that doesn't match .circleci/config.yml",
    ),
    "gitlab_drifts": (
        "gitlab-version-drift",
        "GitLab CI Image Drift",
        "README documentation references a Docker image that doesn't match .gitlab-ci.yml",
    ),
    "k8s_drifts": (
        "kubernetes-version-drift",
        "Kubernetes Image Drift",
        "README documentation references a container image that doesn't match Kubernetes manifests",
    ),
    "helm_drifts": (
        "helm-version-drift",
        "Helm Chart Version Drift",
        "README documentation references a version that doesn't match Chart.yaml or values.yaml",
    ),
    "dc_drifts": (
        "compose-version-drift",
        "Docker Compose Image Drift",
        "README documentation references an image that doesn't match docker-compose.yml",
    ),
    "dotnet_drifts": (
        "dotnet-version-drift",
        ".NET Version Drift",
        "README documentation references a .NET version that doesn't match .csproj TargetFramework",
    ),
    "ruby_drifts": (
        "ruby-version-drift",
        "Ruby Version Drift",
        "README documentation references a Ruby version that doesn't match Gemfile ruby directive",
    ),
    "php_drifts": (
        "php-version-drift",
        "PHP Version Drift",
        "README documentation references a PHP version that doesn't match composer.json require.php",
    ),
    "env_drifts": (
        "env-config-drift",
        "Environment Config Drift",
        "Environment configuration drift detected (.env.example vs .env, Docker Compose overrides, Helm values)",
    ),
    "actions_drifts": (
        "github-actions-node20-deprecated",
        "GitHub Actions Node 20 Deprecation",
        "Workflow uses a GitHub Actions version still pinned to deprecated Node 20 runtime",
    ),
    "gh_actions_version_drifts": (
        "github-actions-version-drift",
        "GitHub Actions Outdated Version",
        "Workflow uses an outdated GitHub Actions version with a newer release available",
    ),
    "ci_os_drifts": (
        "ci-os-deprecated",
        "Deprecated CI Runner",
        "Workflow uses a deprecated GitHub Actions runner (e.g., ubuntu-20.04)",
    ),
    "lineending_drifts": (
        "lineending-drift",
        "Missing Line Ending Configuration",
        "Repository is missing .gitattributes with text=auto eol=lf normalization",
    ),
    "count_drifts": (
        "skills-count-drift",
        "Skills Count Drift",
        "README documentation references a skills/ directory count that doesn't match actual file count",
    ),
    # Informational (non-blocking) — these are warnings
    "external_resource_drifts": (
        "external-resource-drift",
        "External Resource Reference",
        "Documentation references external CDN resources that may break offline/air-gapped rendering",
    ),
    "dependabot_drifts": (
        "dependabot-coverage-drift",
        "Dependabot Coverage Gap",
        "Repository uses package ecosystems not covered by .github/dependabot.yml",
    ),
    "lockfile_drifts": (
        "lockfile-drift",
        "Lockfile Drift",
        "Lockfile is missing, stale, or orphaned relative to its manifest",
    ),
    "engines_drifts": (
        "engines-drift",
        "Engines Drift",
        "package.json engines.node conflicts with .nvmrc or volta.node version",
    ),
    "tool_versions_drifts": (
        "tool-versions-drift",
        "Tool Versions Drift",
        "README documentation references a version that doesn't match .tool-versions (asdf/mise)",
    ),
    "nvmrc_drifts": (
        "nvmrc-drift",
        "NVMRC Version Drift",
        "README documentation references a Node.js version that doesn't match .nvmrc",
    ),
    "swift_drifts": (
        "swift-package-version-drift",
        "Swift Package Version Drift",
        "README documentation references a Swift version that doesn't match Package.swift version pins",
    ),
    "deno_drifts": (
        "deno-version-drift",
        "Deno Version Drift",
        "README documentation references a Deno version that doesn't match deno.json version field",
    ),
    "dart_drifts": (
        "dart-sdk-version-drift",
        "Dart SDK Version Drift",
        "README documentation references a Dart SDK version that doesn't match pubspec.yaml SDK constraint",
    ),
    "makefile_drifts": (
        "makefile-version-drift",
        "Makefile Tool Version Drift",
        "README documentation references a tool version that doesn't match Makefile variable assignments",
    ),
    "elixir_drifts": (
        "elixir-version-drift",
        "Elixir Version Drift",
        "README documentation references an Elixir version that doesn't match mix.exs elixir directive",
    ),
    "cmake_drifts": (
        "cmake-version-drift",
        "CMake Version Drift",
        "README documentation references a CMake version that doesn't match CMakeLists.txt cmake_minimum_required",
    ),
    "requirements_drifts": (
        "requirements-version-drift",
        "Requirements Version Drift",
        "requirements.txt package version doesn't match pyproject.toml or README",
    ),
    "kotlin_drifts": (
        "kotlin-version-drift",
        "Kotlin Version Drift",
        "README documentation references a Kotlin version that doesn't match build.gradle.kts plugin version",
    ),
    "pipfile_drifts": (
        "pipfile-version-drift",
        "Pipfile Version Drift",
        "Pipfile package version doesn't match Pipfile.lock pinned version",
    ),
    "conda_drifts": (
        "conda-unpinned-drift",
        "Conda Unpinned Package",
        "environment.yml contains unpinned package versions",
    ),
    "jenkins_drifts": (
        "jenkins-version-drift",
        "Jenkins Tool Version Drift",
        "README documentation references a tool version that doesn't match Jenkinsfile nodejs/python/docker declarations",
    ),
    "ruby_version_drifts": (
        "ruby-version-file-drift",
        "Ruby Version File Drift",
        "README documentation references a Ruby version that doesn't match .ruby-version",
    ),
    "python_version_drifts": (
        "python-version-file-drift",
        "Python Version File Drift",
        "README documentation references a Python version that doesn't match .python-version",
    ),
    "node_version_drifts": (
        "node-version-file-drift",
        "Node Version File Drift",
        "README documentation references a Node.js version that doesn't match .node-version",
    ),
    "java_version_drifts": (
        "java-version-file-drift",
        "Java Version File Drift",
        "README documentation references a Java version that doesn't match .java-version",
    ),
    "terraform_version_drifts": (
        "terraform-version-file-drift",
        "Terraform Version File Drift",
        "README documentation references a Terraform version that doesn't match .terraform-version",
    ),
    "npmrc_drifts": (
        "npmrc-config-drift",
        "NPMRC Config Drift",
        ".npmrc setting conflicts with package.json (engine-strict, registry, tag-prefix)",
    ),
    "yarnrc_drifts": (
        "yarnrc-version-drift",
        "Yarn RC Version Drift",
        "README documentation references a Yarn version that doesn't match .yml",
    ),
    "pnpm_workspace_drifts": (
        "pnpm-workspace-drift",
        "PNPM Workspace Drift",
        "package.json workspaces do not match pnpm-workspace.yaml",
    ),
    "package_manager_drifts": (
        "package-manager-drift",
        "Package Manager Drift",
        "packageManager field in package.json does not match the lockfile found",
    ),
    "vscode_ext_drifts": (
        "vscode-extensions-drift",
        "VSCode Extensions Drift",
        "README recommends extensions not in .vscode/extensions.json",
    ),
    "editorconfig_drifts": (
        "editorconfig-drift",
        "EditorConfig Drift",
        ".editorconfig settings conflict with README or IDE settings",
    ),
    "git_tag_drifts": (
        "git-tag-drift",
        "Git Tag Drift",
        "README version mentions do not match the latest git tag",
    ),
    "taskfile_drifts": (
        "taskfile-drift",
        "Taskfile Drift",
        "Tasks in Taskfile.yml missing from Makefile, or vice versa",
    ),
    "devcontainer_drifts": (
        "devcontainer-version-drift",
        "Devcontainer Version Drift",
        "README documentation references a version that doesn't match devcontainer.json image or features",
    ),
    "compose_override_drifts": (
        "compose-override-drift",
        "Docker Compose Override Drift",
        "Image version in docker-compose.override.yml (or .prod/.dev) conflicts with docker-compose.yml",
    ),
    "helm_values_drifts": (
        "helm-values-drift",
        "Helm Values Drift",
        "Environment-specific Helm values file (values.prod.yaml) conflicts with default values.yaml",
    ),
    "mise_drifts": (
        "mise-version-drift",
        "Mise Tool Version Drift",
        "README documentation references a tool version that doesn't match mise.toml",
    ),
}

# Drift types that are informational (SARIF level: warning)
INFORMATIONAL_TYPES = {"external_resource_drifts", "dependabot_drifts", "lockfile_drifts", "nvmrc_drifts"}


def _make_rule(rule_id: str, name: str, description: str) -> dict:
    return {
        "id": rule_id,
        "name": name,
        "shortDescription": {"text": description},
        "fullDescription": {"text": description},
        "helpUri": "https://github.com/yunaremaia/driftcheck",
    }


def _make_result(
    rule_id: str,
    message: str,
    file: str,
    *,
    line: int = 1,
    level: str = "warning",
    pos: int = 0,
) -> dict:
    return {
        "ruleId": rule_id,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": file},
                    "region": {"startLine": line, "startColumn": 1},
                }
            }
        ],
        "level": level,
    }


def _drift_message(drift_type: str, d: dict) -> str:
    """Generate human-readable message for a drift entry."""
    if drift_type == "drifts":
        return f"Rust {d.get('doc_version')} in docs should be {d.get('toolchain_version')}"
    elif drift_type == "rust_drifts":
        target = d.get("toolchain_version") or d.get("cargo_version")
        return f"Rust {d.get('doc_version')} in docs should be {target}"
    elif drift_type == "node_drifts":
        return f"Node.js {d.get('doc_version')} in docs should be {d.get('package_version')}"
    elif drift_type == "bun_drifts":
        return f"Bun {d.get('doc_version')} in docs should be {d.get('package_version')}"
    elif drift_type == "python_drifts":
        return f"Python {d.get('doc_version')} in docs should be {d.get('pyproject_version')}"
    elif drift_type == "go_drifts":
        return f"Go {d.get('doc_version')} in docs should be {d.get('gomod_version')}"
    elif drift_type == "docker_drifts":
        return f"Docker image {d.get('doc_image')} in docs should be {d.get('dockerfile_image')}"
    elif drift_type == "docker_multistage_drifts":
        return d.get("detail", "Multi-stage Dockerfile drift detected")
    elif drift_type == "docker_bases_drifts":
        if "tags" in d:
            return f"{d['image']} pinned differently across Dockerfiles: {', '.join(d['tags'])}"
        return f"{d['image']}:{d.get('tag', '(none)')} uses floating/unpinned tag"
    elif drift_type == "java_drifts":
        return f"Java {d.get('doc_version')} in docs should be {d.get('gradle_version')}"
    elif drift_type == "maven_drifts":
        return f"Java {d.get('doc_version')} in docs should be {d.get('maven_version')}"
    elif drift_type == "terraform_drifts":
        return f"Terraform {d.get('provider')} {d.get('doc_version')} in docs should be {d.get('terraform_version')}"
    elif drift_type == "circleci_drifts":
        return f"CircleCI image {d.get('doc_image')} in docs should be {d.get('circleci_image')}"
    elif drift_type == "gitlab_drifts":
        return f"GitLab CI image {d.get('doc_image')} in docs should be {d.get('gitlab_image')}"
    elif drift_type == "k8s_drifts":
        return f"Kubernetes image {d.get('doc_image')} in docs should be {d.get('k8s_image')}"
    elif drift_type == "helm_drifts":
        return f"Helm chart {d.get('doc_version')} in docs should be {d.get('helm_image')}"
    elif drift_type == "dc_drifts":
        return f"Docker Compose {d.get('doc_version')} in docs should be {d.get('compose_image')}"
    elif drift_type == "dotnet_drifts":
        return f".NET {d.get('doc_version')} in docs should be {d.get('csproj_version')}"
    elif drift_type == "ruby_drifts":
        return f"Ruby {d.get('doc_version')} in docs should be {d.get('gemfile_version')}"
    elif drift_type == "php_drifts":
        return f"PHP {d.get('doc_version')} in docs should be {d.get('composer_version')}"
    elif drift_type == "actions_drifts":
        return f"Action {d.get('action')}@{d.get('current')} should be updated to {d.get('action')}@{d.get('suggested')}"
    elif drift_type == "gh_actions_version_drifts":
        return f"Action {d.get('action')}@{d.get('current')} should be updated to {d.get('action')}@{d.get('suggested')}"
    elif drift_type == "ci_os_drifts":
        return f"Runner {d.get('runner')} is deprecated, use {d.get('suggested')}"
    elif drift_type == "lineending_drifts":
        return d.get("detail", "Missing .gitattributes line ending normalization")
    elif drift_type == "count_drifts":
        return f"Docs say {d.get('doc_count')} skills but actual count is {d.get('actual_count')}"
    elif drift_type == "external_resource_drifts":
        return f"External resource: {d.get('detail')} ({d.get('url')})"
    elif drift_type == "dependabot_drifts":
        if d.get("kind") == "dependabot_missing":
            return f"Missing dependabot configuration: {d.get('detail')}"
        return f"Incomplete dependabot coverage: {d.get('detail')}"
    elif drift_type == "lockfile_drifts":
        return d.get("detail", "Lockfile drift detected")
    elif drift_type == "engines_drifts":
        return d.get("detail", "Engines version drift detected")
    elif drift_type == "tool_versions_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('tool_versions_version')} (.tool-versions)"
    elif drift_type == "mise_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('mise_version')} (mise.toml)"
    elif drift_type == "nvmrc_drifts":
        return f"Node {d.get('doc_version')} in docs should be {d.get('nvmrc_version')} (.nvmrc)"
    elif drift_type == "swift_drifts":
        return f"Swift {d.get('doc_version')} in docs should be {d.get('package_version')} (Package.swift)"
    elif drift_type == "deno_drifts":
        return f"Deno {d.get('doc_version')} in docs should be {d.get('deno_json_version')} (deno.json)"
    elif drift_type == "dart_drifts":
        return f"Dart {d.get('doc_version')} in docs should be {d.get('pubspec_version')} (pubspec.yaml)"
    elif drift_type == "makefile_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('makefile_version')} (Makefile)"
    elif drift_type == "elixir_drifts":
        return f"Elixir {d.get('doc_version')} in docs should be {d.get('mix_version')} (mix.exs)"
    elif drift_type == "cmake_drifts":
        return f"CMake {d.get('doc_version')} in docs should be {d.get('cmake_version')} (CMakeLists.txt)"
    elif drift_type == "requirements_drifts":
        return f"{d.get('package', 'package')} {d.get('doc_version')} in docs/requirements should be {d.get('requirements_version')} (requirements.txt)"
    elif drift_type == "kotlin_drifts":
        return f"Kotlin {d.get('doc_version')} in docs should be {d.get('gradle_version')} (build.gradle.kts)"
    elif drift_type == "pipfile_drifts":
        return f"{d.get('package', 'package')}: Pipfile={d.get('pipfile_version')} vs Pipfile.lock={d.get('lock_version')}"
    elif drift_type == "conda_drifts":
        return f"{d.get('package', 'package')}: unpinned version in environment.yml"
    elif drift_type == "ruby_version_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('version_file')} (.ruby-version)"
    elif drift_type == "python_version_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('version_file')} (.python-version)"
    elif drift_type == "node_version_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('version_file')} (.node-version)"
    elif drift_type == "java_version_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('version_file')} (.java-version)"
    elif drift_type == "terraform_version_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('version_file')} (.terraform-version)"
    elif drift_type == "jenkins_drifts":
        return f"{d.get('tool', 'tool')} {d.get('doc_version')} in docs should be {d.get('jenkins_version')} (Jenkinsfile)"
    elif drift_type == "package_manager_drifts":
        return f"packageManager={d.get('package_manager_field')} but {d.get('actual_manager')} lockfile found"
    elif drift_type == "vscode_ext_drifts":
        return d.get("detail", "VSCode extensions drift detected")
    elif drift_type == "editorconfig_drifts":
        return d.get("detail", "EditorConfig drift detected")
    elif drift_type == "git_tag_drifts":
        return d.get("detail", "Git tag drift detected")
    elif drift_type == "taskfile_drifts":
        return d.get("detail", "Taskfile drift detected")
    elif drift_type == "devcontainer_drifts":
        feature = d.get("feature", "image")
        return f"{feature} {d.get('doc_version')} in docs should be {d.get('devcontainer_version')} (devcontainer.json)"
    elif drift_type == "compose_override_drifts":
        return d.get("detail", "Docker Compose override drift detected")
    elif drift_type == "helm_values_drifts":
        key = d.get("key", "value")
        return f"{key}: {d.get('override_value')} in override vs {d.get('default_value')} in values.yaml"
    elif drift_type == "env_drifts":
        return d.get("detail", "Environment config drift detected")
    return str(d)


def to_sarif(result: dict, version: str | None = None) -> dict:
    """Convert driftcheck scan result to SARIF 2.1.0 document."""
    if version is None:
        try:
            from . import __version__ as version
        except ImportError:
            version = "0.1.40"
    rules: list[dict] = []
    results: list[dict] = []
    rule_set: set[str] = set()

    # All possible drift keys in the result
    drift_keys = [
        "drifts", "rust_drifts", "node_drifts", "bun_drifts", "python_drifts",
        "go_drifts", "count_drifts", "actions_drifts", "lineending_drifts",
        "docker_drifts", "docker_multistage_drifts", "docker_bases_drifts", "java_drifts", "maven_drifts", "terraform_drifts",
        "circleci_drifts", "gitlab_drifts", "gh_actions_version_drifts",
        "k8s_drifts", "helm_drifts", "dc_drifts", "ci_os_drifts",
        "dotnet_drifts", "ruby_drifts", "php_drifts",
        "external_resource_drifts", "dependabot_drifts", "lockfile_drifts",
        "engines_drifts",
        "tool_versions_drifts", "nvmrc_drifts", "swift_drifts", "deno_drifts", "dart_drifts", "makefile_drifts", "env_drifts",
        "elixir_drifts", "cmake_drifts", "requirements_drifts", "kotlin_drifts",
        "pipfile_drifts", "conda_drifts",
        "jenkins_drifts",
        "ruby_version_drifts", "python_version_drifts", "node_version_drifts",
        "java_version_drifts", "terraform_version_drifts",
        "npmrc_drifts", "yarnrc_drifts", "pnpm_workspace_drifts", "package_manager_drifts",
        "vscode_ext_drifts", "editorconfig_drifts", "taskfile_drifts",
        "devcontainer_drifts", "compose_override_drifts", "helm_values_drifts",
        "mise_drifts",
    ]

    for drift_type in drift_keys:
        entries = result.get(drift_type, [])
        if not entries:
            continue

        meta = DRIFT_RULES.get(drift_type)
        if not meta:
            continue
        rule_id, rule_name, rule_desc = meta

        if rule_id not in rule_set:
            rules.append(_make_rule(rule_id, rule_name, rule_desc))
            rule_set.add(rule_id)

        is_informational = drift_type in INFORMATIONAL_TYPES
        level = "warning" if is_informational else "error"

        for d in entries:
            file = d.get("file", "")
            message = _drift_message(drift_type, d)
            results.append(
                _make_result(rule_id, message, file, level=level, pos=d.get("pos", 0))
            )

    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "driftcheck",
                        "version": version,
                        "informationUri": "https://github.com/yunaremaia/driftcheck",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
