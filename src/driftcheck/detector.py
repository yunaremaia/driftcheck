"""Detect version drift between docs and toolchain files.

This is a thin orchestrator that imports from the detectors/ subpackage.
All drift detection logic lives in src/driftcheck/detectors/.
"""
from __future__ import annotations
from pathlib import Path
from .detectors import (
    parse_toolchain_version,
    find_rust_drift,
    find_rust_drift_multi,
    parse_cargo_rust_version,
    parse_node_version_from_package,
    find_node_drift,
    parse_python_version_from_pyproject,
    find_python_drift,
    parse_go_version_from_gomod,
    find_go_drift,
    find_docker_drift,
    parse_gradle_java_version,
    find_java_drift,
    parse_maven_java_version,
    find_maven_drift,
    find_terraform_drift,
    find_circleci_drift,
    find_gitlab_drift,
    find_actions_node_drift,
    find_gh_actions_version_drift,
    find_k8s_drift,
    find_helm_drift,
    find_docker_compose_drift,
    parse_dotnet_tfm,
    find_dotnet_drift,
    parse_gemfile_ruby_version,
    find_ruby_drift,
    parse_composer_php_version,
    find_php_drift,
    parse_bun_version_from_package,
    find_bun_drift,
    find_lineending_drift,
    find_external_resource_drift,
    find_count_drift,
    find_dependabot_drift,
    find_ci_os_drift,
    apply_fixes,
)


def scan_repo(root: Path = Path(".")) -> dict:
    """Scan a repo on disk, return {toolchain_version, drifts}."""
    tc_path = root / "rust-toolchain.toml"
    toolchain_text = tc_path.read_text(encoding="utf-8", errors="replace") if tc_path.exists() else ""
    # collect doc files
    candidates = [root / "README.md", root / "CONTRIBUTING.md", root / "CONTRIBUTING-BEGINNERS.md"]
    candidates += list((root / "docs").glob("README*.md"))
    docs = {}
    for p in candidates:
        if p.exists():
            docs[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    pkg_path = root / "package.json"
    package_text = pkg_path.read_text(encoding="utf-8", errors="replace") if pkg_path.exists() else ""
    py_path = root / "pyproject.toml"
    pyproject_text = py_path.read_text(encoding="utf-8", errors="replace") if py_path.exists() else ""
    gomod_path = root / "go.mod"
    gomod_text = gomod_path.read_text(encoding="utf-8", errors="replace") if gomod_path.exists() else ""
    cargo_path = root / "Cargo.toml"
    cargo_text = cargo_path.read_text(encoding="utf-8", errors="replace") if cargo_path.exists() else ""
    
    # Dockerfiles
    dockerfiles = {}
    for pattern in ["Dockerfile", "Dockerfile.*", "docker/Dockerfile", "docker/Dockerfile.*"]:
        for p in root.glob(pattern):
            if p.is_file():
                dockerfiles[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Gradle build files
    gradle_files = {}
    for pattern in ["build.gradle", "build.gradle.kts", "gradle/build.gradle", "gradle/build.gradle.kts"]:
        for p in root.glob(pattern):
            if p.is_file():
                gradle_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Maven pom.xml files
    maven_files = {}
    for pattern in ["pom.xml", "maven/pom.xml"]:
        for p in root.glob(pattern):
            if p.is_file():
                maven_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Terraform files
    terraform_files = {}
    for pattern in ["versions.tf", "*.tf", "terraform/*.tf"]:
        for p in root.glob(pattern):
            if p.is_file():
                terraform_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # CircleCI config files
    circleci_files = {}
    for pattern in [".circleci/config.yml", ".circleci/config.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                circleci_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # GitLab CI config files
    gitlab_files = {}
    for pattern in [".gitlab-ci.yml", ".gitlab-ci.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                gitlab_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    
    # Kubernetes manifests
    k8s_files = {}
    for pattern in ["k8s/**/*.yaml", "k8s/**/*.yml", "kubernetes/**/*.yaml", "kubernetes/**/*.yml", "deploy/**/*.yaml", "deploy/**/*.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                k8s_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    # Docker Compose files
    dc_files = {}
    for pattern in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "docker/docker-compose.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                dc_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")


    # Helm chart files
    helm_files = {}
    for pattern in ["Chart.yaml", "charts/**/Chart.yaml", "values.yaml", "charts/**/values.yaml", "charts/**/values.*.yaml"]:
        for p in root.glob(pattern):
            if p.is_file():
                helm_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    # Ruby project files (Gemfile)
    gemfile_path = root / "Gemfile"
    gemfile_text = gemfile_path.read_text(encoding="utf-8", errors="replace") if gemfile_path.exists() else ""

    # PHP/Composer project files
    composer_path = root / "composer.json"
    composer_text = composer_path.read_text(encoding="utf-8", errors="replace") if composer_path.exists() else ""

    # .NET / C# project files
    csproj_files = {}
    for pattern in ["*.csproj", "**/*.csproj", "src/**/*.csproj", "tests/**/*.csproj"]:
        for p in root.glob(pattern):
            if p.is_file():
                csproj_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    
    rust_drifts = find_rust_drift(toolchain_text, docs)
    rust_drifts_multi = find_rust_drift_multi(toolchain_text, cargo_text, docs)
    node_drifts = find_node_drift(package_text, docs)
    bun_drifts = find_bun_drift(package_text, docs)
    python_drifts = find_python_drift(pyproject_text, docs)
    go_drifts = find_go_drift(gomod_text, docs)
    count_drifts = find_count_drift(root, docs)
    actions_drifts = find_actions_node_drift(root)
    lineending_drifts = find_lineending_drift(root)
    external_resource_drifts = find_external_resource_drift(root)
    docker_drifts = find_docker_drift(dockerfiles, docs)
    java_drifts = find_java_drift("\n".join(gradle_files.values()), docs)
    maven_drifts = find_maven_drift("\n".join(maven_files.values()), docs)
    terraform_drifts = find_terraform_drift(terraform_files, docs)
    circleci_drifts = find_circleci_drift(circleci_files, docs)
    gitlab_drifts = find_gitlab_drift(gitlab_files, docs)
    k8s_drifts = find_k8s_drift(k8s_files, docs)
    helm_drifts = find_helm_drift(helm_files, docs)
    dc_drifts = find_docker_compose_drift(dc_files, docs)
    dependabot_drifts = find_dependabot_drift(root)
    dotnet_drifts = find_dotnet_drift(csproj_files, docs)
    ruby_drifts = find_ruby_drift(gemfile_text, docs)
    php_drifts = find_php_drift(composer_text, docs)
    
    return {
        "toolchain_version": parse_toolchain_version(toolchain_text),
        "cargo_rust_version": parse_cargo_rust_version(cargo_text),
        "package_node": parse_node_version_from_package(package_text),
        "pyproject_python": parse_python_version_from_pyproject(pyproject_text),
        "gomod_version": parse_go_version_from_gomod(gomod_text),
        "drifts": rust_drifts,
        "rust_drifts": rust_drifts_multi,
        "node_drifts": node_drifts,
        "bun_drifts": bun_drifts,
        "python_drifts": python_drifts,
        "go_drifts": go_drifts,
        "count_drifts": count_drifts,
        "actions_drifts": actions_drifts,
        "gh_actions_version_drifts": find_gh_actions_version_drift(root),
        "lineending_drifts": lineending_drifts,
        "external_resource_drifts": external_resource_drifts,
        "docker_drifts": docker_drifts,
        "java_drifts": java_drifts,
        "maven_drifts": maven_drifts,
        "terraform_drifts": terraform_drifts,
        "circleci_drifts": circleci_drifts,
        "gitlab_drifts": gitlab_drifts,
        "helm_drifts": helm_drifts,
        "dc_drifts": dc_drifts,
        "dependabot_drifts": dependabot_drifts,
        "ci_os_drifts": find_ci_os_drift(root),
        "k8s_drifts": k8s_drifts,
        "dotnet_drifts": dotnet_drifts,
        "ruby_drifts": ruby_drifts,
        "php_drifts": php_drifts,
    }


# Re-export all public functions for backward compatibility
__all__ = [
    # Rust
    "parse_toolchain_version",
    "find_rust_drift",
    "find_rust_drift_multi",
    "parse_cargo_rust_version",
    # Node
    "parse_node_version_from_package",
    "find_node_drift",
    # Python
    "parse_python_version_from_pyproject",
    "find_python_drift",
    # Go
    "parse_go_version_from_gomod",
    "find_go_drift",
    # PHP
    "parse_composer_php_version",
    "find_php_drift",
    # Bun
    "parse_bun_version_from_package",
    "find_bun_drift",
    # Docker
    "find_docker_drift",
    # Java/Gradle
    "parse_gradle_java_version",
    "find_java_drift",
    # Maven
    "parse_maven_java_version",
    "find_maven_drift",
    # Terraform
    "find_terraform_drift",
    # CircleCI
    "find_circleci_drift",
    # GitLab
    "find_gitlab_drift",
    # GitHub Actions
    "find_actions_node_drift",
    "find_gh_actions_version_drift",
    # Kubernetes
    "find_k8s_drift",
    # Helm
    "find_helm_drift",
    # Docker Compose
    "find_docker_compose_drift",
    # .NET
    "parse_dotnet_tfm",
    "find_dotnet_drift",
    # Ruby
    "parse_gemfile_ruby_version",
    "find_ruby_drift",
    # Line endings
    "find_lineending_drift",
    # External resources
    "find_external_resource_drift",
    # Count
    "find_count_drift",
    # Dependabot
    "find_dependabot_drift",
    # CI OS
    "find_ci_os_drift",
    # Fix
    "apply_fixes",
    # Orchestrator
    "scan_repo",
]
