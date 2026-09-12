"""Detect version drift between docs and toolchain files.

This is a thin orchestrator that imports from the detectors/ subpackage.
All drift detection logic lives in src/driftcheck/detectors/.

Configuration:
    driftcheck supports a `.driftcheck.toml` file in repo root for
    customizing detection behavior. See README for details.

Performance:
    File I/O is parallelized via ThreadPoolExecutor for large repos.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import load_config, get_excluded_detectors
from .plugins import load_plugins, run_plugin_detectors
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
    find_dockerfile_bases_drift,
    parse_from_stages,
    find_dockerfile_multistage_drift,
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
    find_lockfile_drift,
    find_engines_drift,
    find_tool_versions_drift,
    find_nvmrc_drift,
    parse_deno_version,
    find_deno_drift,
    parse_swift_version_from_package,
    find_swift_drift,
    parse_dart_sdk_version,
    find_dart_drift,
    parse_makefile_versions,
    find_makefile_drift,
    parse_mix_elixir_version,
    find_elixir_drift,
    parse_cmake_version,
    find_cmake_drift,
    find_env_drift,
    find_compose_override_drift,
    find_helm_values_drift,
    find_env_drift_combined,
    find_requirements_drift,
    parse_kotlin_version,
    find_kotlin_drift,
    find_pipfile_drift,
    find_conda_drift,
    find_gradle_catalog_drift,
    parse_jenkins_node_agent,
    parse_jenkins_nodejs_version,
    parse_jenkins_python_version,
    parse_jenkins_docker_images,
    find_jenkins_drift,
    parse_ruby_version,
    parse_python_version,
    parse_node_version,
    parse_java_version,
    parse_terraform_version,
    find_version_file_drift,
    apply_fixes,
    parse_npmrc,
    find_npmrc_drift,
    parse_yarnrc_version,
    find_yarnrc_drift,
    parse_pnpm_workspace,
    find_pnpm_workspace_drift,
    parse_package_manager_field,
    detect_lockfile_manager,
    find_package_manager_drift,
    parse_vscode_extensions,
    find_vscode_extensions_drift,
    get_latest_git_tag,
    find_git_tag_drift,
    parse_editorconfig,
    find_editorconfig_drift,
    find_devcontainer_drift,
    find_taskfile_drift,
    find_mise_drift,
    parse_mise_tools,
)


def _read_files_parallel(root: Path, patterns: list[str]) -> str:
    """Read multiple files in parallel using ThreadPoolExecutor.
    
    Returns concatenated file contents separated by newlines.
    """
    files = []
    for pattern in patterns:
        for p in root.glob(pattern):
            if p.is_file():
                files.append(p)
    
    if not files:
        return ""
    
    contents = []
    with ThreadPoolExecutor(max_workers=min(8, len(files))) as executor:
        futures = {
            executor.submit(lambda p=p: p.read_text(encoding="utf-8", errors="replace")): p
            for p in files
        }
        for future in as_completed(futures):
            try:
                contents.append(future.result())
            except Exception:
                pass
    return "\n".join(contents)


def scan_repo(root: Path = Path("."), enabled_detectors: set[str] | None = None) -> dict:
    """Scan a repo on disk, return {toolchain_version, drifts}.

    Configuration is loaded from .driftcheck.toml if present.
    File I/O is parallelized via ThreadPoolExecutor for large repos.
    
    Args:
        root: repo root path
        enabled_detectors: if set, only run these detector keys (skip others)
    """
    config = load_config(root)
    excluded = get_excluded_detectors(config)

    # Filter detectors if git-mode is active
    if enabled_detectors is not None:
        excluded = excluded | (set(DRIFT_KEYS) - enabled_detectors)

    tc_path = root / "rust-toolchain.toml"
    toolchain_text = tc_path.read_text(encoding="utf-8", errors="replace") if tc_path.exists() else ""
    # collect doc files
    candidates = [root / "README.md", root / "CONTRIBUTING.md", root / "CONTRIBUTING-BEGINNERS.md"]
    candidates += list((root / "docs").glob("README*.md"))
    # Support custom doc_paths from config
    custom_doc_paths = config.get("doc_paths")
    if custom_doc_paths:
        for pattern in custom_doc_paths:
            for p in root.glob(pattern):
                if p.is_file():
                    candidates.append(p)
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

    # Mise.toml (successor to .tool-versions / asdf)
    mise_path = root / "mise.toml"
    mise_text = mise_path.read_text(encoding="utf-8", errors="replace") if mise_path.exists() else ""

    # .tool-versions (asdf/mise)
    tv_path = root / ".tool-versions"
    tool_versions_text = tv_path.read_text(encoding="utf-8", errors="replace") if tv_path.exists() else ""

    # .nvmrc
    nvmrc_path = root / ".nvmrc"
    nvmrc_text = nvmrc_path.read_text(encoding="utf-8", errors="replace") if nvmrc_path.exists() else ""

    # .NET / C# project files
    csproj_files = {}
    for pattern in ["*.csproj", "**/*.csproj", "src/**/*.csproj", "tests/**/*.csproj"]:
        for p in root.glob(pattern):
            if p.is_file():
                csproj_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    # Swift Package Manager
    swift_path = root / "Package.swift"
    swift_text = swift_path.read_text(encoding="utf-8", errors="replace") if swift_path.exists() else ""

    # Dart/Flutter pubspec
    pubspec_files = {}
    for pattern in ["pubspec.yaml", "pubspec.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                pubspec_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    pubspec_text = "\n".join(pubspec_files.values()) if pubspec_files else ""

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
    docker_multistage_drifts = find_dockerfile_multistage_drift(dockerfiles, docs)
    docker_bases_drifts = find_dockerfile_bases_drift(dockerfiles, docs)
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
    lockfile_drifts = find_lockfile_drift(root)
    engines_drifts = find_engines_drift(root)
    tool_versions_drifts = find_tool_versions_drift(tool_versions_text, docs)
    mise_drifts = find_mise_drift(mise_text, docs)
    nvmrc_drifts = find_nvmrc_drift(nvmrc_text, parse_node_version_from_package(package_text), docs)
    swift_drifts = find_swift_drift(swift_text, docs)

    # Dart/Flutter
    dart_drifts = find_dart_drift(pubspec_text, docs)

    # Deno
    deno_files = {}
    for pattern in ["deno.json", "deno.jsonc", "deno/deno.json", "deno/deno.jsonc"]:
        for p in root.glob(pattern):
            if p.is_file():
                deno_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    deno_text = "\n".join(deno_files.values()) if deno_files else ""
    deno_drifts = find_deno_drift(deno_text, docs)

    # Makefile
    makefile_files = {}
    for pattern in ["Makefile", "makefile", "GNUmakefile", "make/*.mk", "Makefile.*"]:
        for p in root.glob(pattern):
            if p.is_file():
                makefile_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    makefile_text = "\n".join(makefile_files.values()) if makefile_files else ""
    makefile_drifts = find_makefile_drift(makefile_text, docs)

    # Elixir
    mix_path = root / "mix.exs"
    mix_text = mix_path.read_text(encoding="utf-8", errors="replace") if mix_path.exists() else ""
    elixir_drifts = find_elixir_drift(mix_text, docs)

    # CMake
    cmake_files = {}
    for pattern in ["CMakeLists.txt", "cmake/CMakeLists.txt", "src/CMakeLists.txt"]:
        for p in root.glob(pattern):
            if p.is_file():
                cmake_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    cmake_text = "\n".join(cmake_files.values()) if cmake_files else ""
    cmake_drifts = find_cmake_drift(cmake_text, docs)

    # Requirements.txt
    req_path = root / "requirements.txt"
    req_text = req_path.read_text(encoding="utf-8", errors="replace") if req_path.exists() else ""
    requirements_drifts = find_requirements_drift(req_text, pyproject_text, docs)

    # Kotlin (build.gradle.kts)
    gradle_kts_files = {}
    for pattern in ["build.gradle.kts", "gradle/build.gradle.kts"]:
        for p in root.glob(pattern):
            if p.is_file():
                gradle_kts_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    gradle_kts_text = "\n".join(gradle_kts_files.values()) if gradle_kts_files else ""
    kotlin_drifts = find_kotlin_drift(gradle_kts_text, docs)

    # Pipfile
    pipfile_drifts = find_pipfile_drift(root)

    # Conda
    conda_drifts = find_conda_drift(root)
    # Gradle Version Catalog
    gradle_catalog_drifts = find_gradle_catalog_drift(root)

    # Jenkins
    jenkins_files = {}
    seen_jenkins_paths = set()
    for pattern in ["Jenkinsfile", "jenkins/Jenkinsfile", "Jenkinsfile.*"]:
        for p in root.glob(pattern):
            if p.is_file() and p not in seen_jenkins_paths:
                seen_jenkins_paths.add(p)
                jenkins_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    jenkins_drifts = find_jenkins_drift(jenkins_files, docs)

    # Version files (.ruby-version, .python-version, .node-version, .java-version, .terraform-version)
    version_files = {}
    for pattern in [".ruby-version", ".python-version", ".node-version", ".java-version", ".terraform-version"]:
        for p in root.glob(pattern):
            if p.is_file():
                version_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")

    ruby_version_drifts = find_version_file_drift(version_files, docs, "Ruby")
    python_version_drifts = find_version_file_drift(version_files, docs, "Python")
    node_version_drifts = find_version_file_drift(version_files, docs, "Node.js")
    java_version_drifts = find_version_file_drift(version_files, docs, "Java")
    terraform_version_drifts = find_version_file_drift(version_files, docs, "Terraform")

    # NPMRC
    npmrc_path = root / ".npmrc"
    npmrc_text = npmrc_path.read_text(encoding="utf-8", errors="replace") if npmrc_path.exists() else None
    npmrc_drifts = find_npmrc_drift(npmrc_text, package_text or None, docs)

    # Yarn RC
    yarnrc_path = root / ".yarnrc.yml"
    yarnrc_text = yarnrc_path.read_text(encoding="utf-8", errors="replace") if yarnrc_path.exists() else None
    yarnrc_drifts = find_yarnrc_drift(yarnrc_text, docs)

    # PNPM workspace
    pnpm_workspace_path = root / "pnpm-workspace.yaml"
    pnpm_workspace_text = pnpm_workspace_path.read_text(encoding="utf-8", errors="replace") if pnpm_workspace_path.exists() else None
    pnpm_workspace_drifts = find_pnpm_workspace_drift(pnpm_workspace_text, package_text or None, docs)

    # Package manager drift (packageManager field vs lockfile)
    package_manager_drifts = find_package_manager_drift(package_text or None, root, docs)

    # VSCode extensions drift
    vscode_ext_path = root / ".vscode" / "extensions.json"
    vscode_ext_text = vscode_ext_path.read_text(encoding="utf-8", errors="replace") if vscode_ext_path.exists() else None
    vscode_ext_drifts = find_vscode_extensions_drift(vscode_ext_text, docs)

    # EditorConfig drift
    editorconfig_path = root / ".editorconfig"
    editorconfig_text = editorconfig_path.read_text(encoding="utf-8", errors="replace") if editorconfig_path.exists() else None
    vscode_settings_path = root / ".vscode" / "settings.json"
    vscode_settings_text = vscode_settings_path.read_text(encoding="utf-8", errors="replace") if vscode_settings_path.exists() else None
    editorconfig_drifts = find_editorconfig_drift(editorconfig_text, docs, vscode_settings_text)

    # Taskfile
    taskfile_drifts = find_taskfile_drift(root)

    # Git tag drift (latest git tag vs README)
    git_tag_drifts = find_git_tag_drift(root, docs)

    # Devcontainer
    devcontainer_files = {}
    for pattern in [".devcontainer/devcontainer.json", ".devcontainer/*.devcontainer.json", "devcontainer.json"]:
        for p in root.glob(pattern):
            if p.is_file():
                devcontainer_files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    devcontainer_text = "\n".join(devcontainer_files.values()) if devcontainer_files else ""
    devcontainer_drifts = find_devcontainer_drift(devcontainer_text, docs)

    result = {
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
        "docker_multistage_drifts": docker_multistage_drifts,
        "docker_bases_drifts": docker_bases_drifts,
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
        "env_drifts": find_env_drift_combined(root),
        "env_example_drifts": find_env_drift(root),
        "compose_override_drifts": find_compose_override_drift(root),
        "helm_values_drifts": find_helm_values_drift(root),
        "lockfile_drifts": lockfile_drifts,
        "engines_drifts": engines_drifts,
        "tool_versions_drifts": tool_versions_drifts,
        "mise_drifts": mise_drifts,
        "nvmrc_drifts": nvmrc_drifts,
        "swift_drifts": swift_drifts,
        "deno_drifts": deno_drifts,
        "dart_drifts": dart_drifts,
        "makefile_drifts": makefile_drifts,
        "elixir_drifts": elixir_drifts,
        "cmake_drifts": cmake_drifts,
        "requirements_drifts": requirements_drifts,
        "kotlin_drifts": kotlin_drifts,
        "pipfile_drifts": pipfile_drifts,
        "conda_drifts": conda_drifts,
        "gradle_catalog_drifts": gradle_catalog_drifts,
        "jenkins_drifts": jenkins_drifts,
        "ruby_version_drifts": ruby_version_drifts,
        "python_version_drifts": python_version_drifts,
        "node_version_drifts": node_version_drifts,
        "java_version_drifts": java_version_drifts,
        "terraform_version_drifts": terraform_version_drifts,
        "npmrc_drifts": npmrc_drifts,
        "yarnrc_drifts": yarnrc_drifts,
        "pnpm_workspace_drifts": pnpm_workspace_drifts,
        "package_manager_drifts": package_manager_drifts,
        "vscode_ext_drifts": vscode_ext_drifts,
        "editorconfig_drifts": editorconfig_drifts,
        "git_tag_drifts": git_tag_drifts,
        "devcontainer_drifts": devcontainer_drifts,
        "taskfile_drifts": taskfile_drifts,
    }

    # Run plugin detectors
    plugins = load_plugins(root)
    plugin_results = run_plugin_detectors(root, docs, plugins)
    result.update(plugin_results)

    # Apply excluded detectors filter
    for key in list(result.keys()):
        if key in excluded:
            del result[key]

    return result


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
    "find_dockerfile_bases_drift",
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
    # Lockfile
    "find_lockfile_drift",
    # Engines
    "find_engines_drift",
    # Tool versions (asdf/mise)
    "parse_tool_versions",
    "find_tool_versions_drift",
    # NVMRC
    "parse_nvmrc_version",
    "find_nvmrc_drift",
    # Deno
    "parse_deno_version",
    "find_deno_drift",
    # Swift
    "parse_swift_version_from_package",
    "find_swift_drift",
    # Dart
    "parse_dart_sdk_version",
    "find_dart_drift",
    # Fix
    "apply_fixes",
    # Devcontainer
    "find_devcontainer_drift",
    # Environment drift
    "find_env_drift_combined",
    # Orchestrator
    "scan_repo",
]
