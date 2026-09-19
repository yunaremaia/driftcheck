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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import warnings

from .config import DRIFT_KEYS, get_excluded_detectors, load_config, get_ignore_patterns, _matches_ignore_patterns
from .plugins import load_plugins, run_plugin_detectors
from .detectors.rust_workspace import find_rust_workspace_drift


def _walk_files(root: Path, follow_symlinks: bool = True) -> tuple[set[Path], list[str]]:
    """Walk directory tree, respecting symlink policy.

    Symlinks pointing outside the repo root are NEVER followed, regardless
    of follow_symlinks setting. This prevents path traversal attacks.

    Args:
        root: repo root path
        follow_symlinks: if False, skip all symlinks

    Returns:
        Tuple of (file_paths, skipped_symlinks) where skipped_symlinks are
        human-readable strings describing skipped links for SARIF output.
    """
    files: set[Path] = set()
    skipped: list[str] = []
    root_resolved = root.resolve()

    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_path = Path(dirpath)
        for fname in filenames:
            fpath = dirpath_path / fname
            if fpath.is_symlink():
                try:
                    target = fpath.resolve()
                    # Never follow symlinks outside repo root
                    if not str(target).startswith(str(root_resolved)):
                        skipped.append(
                            f"Symlink '{fpath.relative_to(root)}' skipped (outside repo root)"
                        )
                        continue
                    if follow_symlinks:
                        files.add(fpath)
                    else:
                        skipped.append(
                            f"Symlink '{fpath.relative_to(root)}' skipped (follow_symlinks=False)"
                        )
                except (OSError, RuntimeError):
                    skipped.append(
                        f"Symlink '{fpath.relative_to(root)}' skipped (broken, inaccessible, or symlink loop)"
                    )
            else:
                files.add(fpath)
    return files, skipped


def _safe_glob(root: Path, pattern: str, walked_files: set[Path], follow_symlinks: bool = True):
    """Wrap Path.glob to respect symlink policy.

    When follow_symlinks is False, only yield files that appear in walked_files
    (i.e., files found by os.walk which skips external symlinks). Paths that are
    symlinks pointing outside root are excluded.
    """
    root_resolved = root.resolve()
    for p in root.glob(pattern):
        if follow_symlinks:
            yield p
            continue
        # follow_symlinks is False: check symlink safety
        if p.is_symlink():
            try:
                target = p.resolve()
                if str(target).startswith(str(root_resolved)):
                    yield p
                continue
            except (OSError, RuntimeError):
                continue
        if p in walked_files:
            yield p


def _read_text_safe(path: Path, max_size: int = 1_000_000) -> str | None:
    """Read text file safely, returning None if too large, binary, or unreadable.

    Args:
        path: file path to read
        max_size: maximum file size in bytes (default 1MB)

    Returns:
        File contents as string, or None if file doesn't exist, is too large,
        binary content, or unreadable.
    """
    try:
        if not path.exists():
            return None
        size = path.stat().st_size
        if size > max_size:
            return None
        # Check for binary content (null bytes in first 8KB)
        with open(path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


from .detectors import (
    apply_fixes,
    find_actions_node_drift,
    find_bazel_drift,
    find_bun_drift,
    find_ci_os_drift,
    find_circleci_drift,
    find_cmake_drift,
    find_compose_override_drift,
    find_conda_drift,
    find_count_drift,
    find_dart_drift,
    find_deno_drift,
    find_dependabot_drift,
    find_devcontainer_drift,
    find_docker_compose_drift,
    find_docker_drift,
    find_dockerfile_bases_drift,
    find_dockerfile_instruction_drift,
    find_dockerfile_multistage_drift,
    find_dotnet_drift,
    find_editorconfig_drift,
    find_elixir_drift,
    find_engines_drift,
    find_env_drift,
    find_env_drift_combined,
    find_external_resource_drift,
    find_gh_actions_version_drift,
    find_git_tag_drift,
    find_gitlab_drift,
    find_go_drift,
    find_gradle_catalog_drift,
    find_helm_drift,
    find_helm_values_drift,
    find_java_drift,
    find_jenkins_drift,
    find_k8s_drift,
    find_kotlin_drift,
    find_kotlin_multiplatform_drift,
    find_lineending_drift,
    find_lockfile_drift,
    find_makefile_drift,
    find_maven_drift,
    find_mise_drift,
    find_nix_drift,
    find_node_drift,
    find_npmrc_drift,
    find_nvmrc_drift,
    find_package_manager_drift,
    find_php_drift,
    find_pipfile_drift,
    find_pnpm_workspace_drift,
    find_poetry_drift,
    find_pre_commit_drift,
    find_python_drift,
    find_python_version_file_drift,
    find_renovate_drift,
    find_requirements_drift,
    find_ruby_drift,
    find_rust_drift,
    find_rust_drift_multi,
    find_swift_drift,
    find_taskfile_drift,
    find_terraform_drift,
    find_tool_versions_drift,
    find_typosquat_drift,
    find_version_file_drift,
    find_vscode_extensions_drift,
    find_yarnrc_drift,
    parse_bun_version_from_package,
    parse_cargo_rust_version,
    parse_composer_php_version,
    parse_dart_sdk_version,
    parse_deno_version,
    parse_dotnet_tfm,
    parse_gemfile_ruby_version,
    parse_go_version_from_gomod,
    parse_gradle_java_version,
    parse_maven_java_version,
    parse_node_version_from_package,
    parse_python_version_from_pyproject,
    parse_swift_version_from_package,
    parse_toolchain_version,
)


def _read_files_parallel(root: Path, patterns: list[str]) -> str:
    """Read multiple files in parallel using ThreadPoolExecutor.

    Returns concatenated file contents separated by newlines.
    Files that fail to read are logged to stderr via warnings.
    """
    files = []
    for pattern in patterns:
        for p in root.glob(pattern):
            if p.is_file():
                files.append(p)

    if not files:
        return ""

    contents = []
    failed = []
    with ThreadPoolExecutor(max_workers=min(8, len(files))) as executor:
        futures = {
            executor.submit(_read_text_safe, p, max_size=1_000_000): p
            for p in files
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                result = future.result()
                if result is not None:
                    contents.append(result)
            except Exception as e:
                failed.append(f"{path}: {e}")
    if failed:
        warnings.warn(
            f"_read_files_parallel: {len(failed)} file(s) failed to read: {'; '.join(failed[:5])}{'...' if len(failed) > 5 else ''}",
            stacklevel=2,
        )
    return "\n".join(contents)


def scan_repo(root: Path = Path("."), enabled_detectors: set[str] | None = None, max_file_size: int | None = None) -> dict:
    """Scan a repo on disk, return {toolchain_version, drifts}.

    Configuration is loaded from .driftcheck.toml if present.
    File I/O is parallelized via ThreadPoolExecutor for large repos.

    Args:
        root: repo root path
        enabled_detectors: if set, only run these detector keys (skip others)
        max_file_size: override max file size in bytes (default from config: 1MB)
    """
    config = load_config(root)
    excluded = get_excluded_detectors(config)
    follow_symlinks = config.get("follow_symlinks", True)
    default_max_size = 1_000_000  # 1MB fallback
    max_file_size = max_file_size or config.get("max_file_size", default_max_size)

    # Walk files with symlink policy (issue #128)
    walked_files, skipped_symlinks = _walk_files(root, follow_symlinks=follow_symlinks)

    # Apply ignore_patterns to filter files before detector runs
    ignore_patterns = get_ignore_patterns(config)
    if ignore_patterns:
        walked_files = {p for p in walked_files if not _matches_ignore_patterns(p.relative_to(root).as_posix(), ignore_patterns)}

    # Filter detectors if git-mode is active
    if enabled_detectors is not None:
        excluded = excluded | (set(DRIFT_KEYS) - enabled_detectors)

    tc_path = root / "rust-toolchain.toml"
    toolchain_text = _read_text_safe(tc_path, max_size=max_file_size) or ""
    # collect doc files
    candidates = [root / "README.md", root / "CONTRIBUTING.md", root / "CONTRIBUTING-BEGINNERS.md"]
    candidates += list((root / "docs").glob("README*.md"))
    # Support custom doc_paths from config
    custom_doc_paths = config.get("doc_paths")
    if custom_doc_paths:
        for pattern in custom_doc_paths:
            for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
                if p.is_file():
                    candidates.append(p)
    docs = {}
    for p in candidates:
        if p.exists():
            content = _read_text_safe(p, max_size=max_file_size)
            if content is not None:
                docs[p.relative_to(root).as_posix()] = content
    pkg_path = root / "package.json"
    package_text = _read_text_safe(pkg_path, max_size=max_file_size) or ""
    py_path = root / "pyproject.toml"
    pyproject_text = _read_text_safe(py_path, max_size=max_file_size) or ""
    gomod_path = root / "go.mod"
    gomod_text = _read_text_safe(gomod_path, max_size=max_file_size) or ""
    cargo_path = root / "Cargo.toml"
    cargo_text = _read_text_safe(cargo_path, max_size=max_file_size) or ""

    # Dockerfiles (respect follow_symlinks policy)
    dockerfiles = {}
    for pattern in ["Dockerfile", "Dockerfile.*", "docker/Dockerfile", "docker/Dockerfile.*"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    dockerfiles[p.relative_to(root).as_posix()] = content

    # Gradle build files
    gradle_files = {}
    for pattern in ["build.gradle", "build.gradle.kts", "gradle/build.gradle", "gradle/build.gradle.kts"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    gradle_files[p.relative_to(root).as_posix()] = content

    # Maven pom.xml files
    maven_files = {}
    for pattern in ["pom.xml", "maven/pom.xml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    maven_files[p.relative_to(root).as_posix()] = content

    # Terraform files
    terraform_files = {}
    for pattern in ["versions.tf", "*.tf", "terraform/*.tf"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    terraform_files[p.relative_to(root).as_posix()] = content

    # CircleCI config files
    circleci_files = {}
    for pattern in [".circleci/config.yml", ".circleci/config.yaml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    circleci_files[p.relative_to(root).as_posix()] = content

    # GitLab CI config files
    gitlab_files = {}
    for pattern in [".gitlab-ci.yml", ".gitlab-ci.yaml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    gitlab_files[p.relative_to(root).as_posix()] = content

    # Kubernetes manifests
    k8s_files = {}
    for pattern in ["k8s/**/*.yaml", "k8s/**/*.yml", "kubernetes/**/*.yaml", "kubernetes/**/*.yml", "deploy/**/*.yaml", "deploy/**/*.yml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and (follow_symlinks or p in walked_files):
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    k8s_files[p.relative_to(root).as_posix()] = content

    # Docker Compose files (respect follow_symlinks policy)
    dc_files = {}
    for pattern in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "docker/docker-compose.yml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    dc_files[p.relative_to(root).as_posix()] = content


    # Helm chart files (respect follow_symlinks policy)
    helm_files = {}
    for pattern in ["Chart.yaml", "charts/**/Chart.yaml", "values.yaml", "charts/**/values.yaml", "charts/**/values.*.yaml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    helm_files[p.relative_to(root).as_posix()] = content

    # Ruby project files (Gemfile)
    gemfile_path = root / "Gemfile"
    gemfile_text = _read_text_safe(gemfile_path, max_size=max_file_size) or ""

    # PHP/Composer project files
    composer_path = root / "composer.json"
    composer_text = _read_text_safe(composer_path, max_size=max_file_size) or ""

    # Mise.toml (successor to .tool-versions / asdf)
    mise_path = root / "mise.toml"
    mise_text = _read_text_safe(mise_path, max_size=max_file_size) or ""

    # .tool-versions (asdf/mise)
    tv_path = root / ".tool-versions"
    tool_versions_text = _read_text_safe(tv_path, max_size=max_file_size) or ""

    # .nvmrc
    nvmrc_path = root / ".nvmrc"
    nvmrc_text = _read_text_safe(nvmrc_path, max_size=max_file_size) or ""

    # .NET / C# project files (respect follow_symlinks policy)
    csproj_files = {}
    for pattern in ["*.csproj", "**/*.csproj", "src/**/*.csproj", "tests/**/*.csproj"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    csproj_files[p.relative_to(root).as_posix()] = content

    # Swift Package Manager
    swift_path = root / "Package.swift"
    swift_text = _read_text_safe(swift_path, max_size=max_file_size) or ""

    # Dart/Flutter pubspec
    pubspec_files = {}
    for pattern in ["pubspec.yaml", "pubspec.yml"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    pubspec_files[p.relative_to(root).as_posix()] = content
    pubspec_text = "\n".join(pubspec_files.values()) if pubspec_files else ""

    rust_drifts_multi = find_rust_drift_multi(toolchain_text, cargo_text, docs)
    rust_workspace_drifts = find_rust_workspace_drift(root)
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
    dockerfile_instruction_drifts = find_dockerfile_instruction_drift(dockerfiles, docs)
    java_drifts = find_java_drift("\n".join(gradle_files.values()), docs)
    maven_drifts = find_maven_drift("\n".join(maven_files.values()), docs)
    terraform_drifts = find_terraform_drift(terraform_files, docs)
    circleci_drifts = find_circleci_drift(circleci_files, docs)
    gitlab_drifts = find_gitlab_drift(gitlab_files, docs)
    k8s_drifts = find_k8s_drift(k8s_files, docs)
    helm_drifts = find_helm_drift(helm_files, docs)
    dc_drifts = find_docker_compose_drift(dc_files, docs)
    dependabot_drifts = find_dependabot_drift(root)
    typosquat_drifts = find_typosquat_drift(root)
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
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    deno_files[p.relative_to(root).as_posix()] = content
    deno_text = "\n".join(deno_files.values()) if deno_files else ""
    deno_drifts = find_deno_drift(deno_text, docs)

    # Makefile
    makefile_files = {}
    for pattern in ["Makefile", "makefile", "GNUmakefile", "make/*.mk", "Makefile.*"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    makefile_files[p.relative_to(root).as_posix()] = content

    makefile_text = "\n".join(makefile_files.values()) if makefile_files else ""
    makefile_drifts = find_makefile_drift(makefile_text, docs)

    # Elixir
    mix_path = root / "mix.exs"
    mix_text = _read_text_safe(mix_path, max_size=max_file_size) or ""
    elixir_drifts = find_elixir_drift(mix_text, docs)

    # CMake
    cmake_files = {}
    for pattern in ["CMakeLists.txt", "cmake/CMakeLists.txt", "src/CMakeLists.txt"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    cmake_files[p.relative_to(root).as_posix()] = content
    cmake_text = "\n".join(cmake_files.values()) if cmake_files else ""
    cmake_drifts = find_cmake_drift(cmake_text, docs)

    # Requirements.txt
    req_path = root / "requirements.txt"
    req_text = _read_text_safe(req_path, max_size=max_file_size) or ""
    requirements_drifts = find_requirements_drift(req_text, pyproject_text, docs)
    bazel_drifts = find_bazel_drift(root)
    nix_drifts = find_nix_drift(root)

    # Poetry (pyproject.toml with [tool.poetry] section)
    poetry_pyproject_path = root / "pyproject.toml"
    poetry_pyproject_text = _read_text_safe(poetry_pyproject_path, max_size=max_file_size) or ""
    poetry_drifts = find_poetry_drift(poetry_pyproject_text, docs)

    # Kotlin (build.gradle.kts)
    gradle_kts_files = {}
    for pattern in ["build.gradle.kts", "gradle/build.gradle.kts"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    gradle_kts_files[p.relative_to(root).as_posix()] = content
    gradle_kts_text = "\n".join(gradle_kts_files.values()) if gradle_kts_files else ""
    kotlin_drifts = find_kotlin_drift(gradle_kts_text, docs)

    # Pipfile
    pipfile_drifts = find_pipfile_drift(root)

    # Conda
    conda_drifts = find_conda_drift(root)
    # Gradle Version Catalog
    gradle_catalog_drifts = find_gradle_catalog_drift(root)

    # Kotlin Multiplatform (KMP) drift: libs.versions.toml vs README badges
    kmp_drifts = find_kotlin_multiplatform_drift(root)

    # Jenkins
    jenkins_files = {}
    seen_jenkins_paths = set()
    for pattern in ["Jenkinsfile", "jenkins/Jenkinsfile", "Jenkinsfile.*"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file() and p not in seen_jenkins_paths:
                seen_jenkins_paths.add(p)
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    jenkins_files[p.relative_to(root).as_posix()] = content

    jenkins_drifts = find_jenkins_drift(jenkins_files, docs)

    # Version files (.ruby-version, .python-version, .node-version, .java-version, .terraform-version)
    version_files = {}
    for pattern in [".ruby-version", ".python-version", ".node-version", ".java-version", ".terraform-version"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    version_files[p.relative_to(root).as_posix()] = content

    # Python version file drift (.python-version vs requires-python floor)
    setup_cfg_path = root / "setup.cfg"
    setup_cfg_text = _read_text_safe(setup_cfg_path, max_size=max_file_size)
    setup_py_path = root / "setup.py"
    setup_py_text = _read_text_safe(setup_py_path, max_size=max_file_size)
    python_version_file_drifts = find_python_version_file_drift(
        version_files.get(".python-version"),
        pyproject_text or None,
        setup_cfg_text,
        setup_py_text,
    )

    ruby_version_drifts = find_version_file_drift(version_files, docs, "Ruby")
    python_version_drifts = find_version_file_drift(version_files, docs, "Python")
    node_version_drifts = find_version_file_drift(version_files, docs, "Node.js")
    java_version_drifts = find_version_file_drift(version_files, docs, "Java")
    terraform_version_drifts = find_version_file_drift(version_files, docs, "Terraform")

    # NPMRC
    npmrc_path = root / ".npmrc"
    npmrc_text = _read_text_safe(npmrc_path, max_size=max_file_size)
    npmrc_drifts = find_npmrc_drift(npmrc_text, package_text or None, docs)

    # Yarn RC
    yarnrc_path = root / ".yarnrc.yml"
    yarnrc_text = _read_text_safe(yarnrc_path, max_size=max_file_size)
    yarnrc_drifts = find_yarnrc_drift(yarnrc_text, docs)

    # PNPM workspace
    pnpm_workspace_path = root / "pnpm-workspace.yaml"
    pnpm_workspace_text = _read_text_safe(pnpm_workspace_path, max_size=max_file_size)
    pnpm_workspace_drifts = find_pnpm_workspace_drift(pnpm_workspace_text, package_text or None, docs)

    # Package manager drift (packageManager field vs lockfile)
    package_manager_drifts = find_package_manager_drift(package_text or None, root, docs)

    # VSCode extensions drift
    vscode_ext_path = root / ".vscode" / "extensions.json"
    vscode_ext_text = _read_text_safe(vscode_ext_path, max_size=max_file_size)
    vscode_ext_drifts = find_vscode_extensions_drift(vscode_ext_text, docs)

    # EditorConfig drift
    editorconfig_path = root / ".editorconfig"
    editorconfig_text = _read_text_safe(editorconfig_path, max_size=max_file_size)
    vscode_settings_path = root / ".vscode" / "settings.json"
    vscode_settings_text = _read_text_safe(vscode_settings_path, max_size=max_file_size)
    editorconfig_drifts = find_editorconfig_drift(editorconfig_text, docs, vscode_settings_text)

    # Taskfile
    taskfile_drifts = find_taskfile_drift(root)

    # Git tag drift (latest git tag vs README)
    git_tag_drifts = find_git_tag_drift(root, docs)

    # Pre-commit config drift
    pre_commit_path = root / ".pre-commit-config.yaml"
    pre_commit_text = _read_text_safe(pre_commit_path, max_size=max_file_size) or ""
    pre_commit_drifts = find_pre_commit_drift(pre_commit_text, docs)

    # Devcontainer
    devcontainer_files = {}
    for pattern in [".devcontainer/devcontainer.json", ".devcontainer/*.devcontainer.json", "devcontainer.json"]:
        for p in _safe_glob(root, pattern, walked_files, follow_symlinks):
            if p.is_file():
                content = _read_text_safe(p, max_size=max_file_size)
                if content is not None:
                    devcontainer_files[p.relative_to(root).as_posix()] = content
    devcontainer_text = "\n".join(devcontainer_files.values()) if devcontainer_files else ""
    devcontainer_drifts = find_devcontainer_drift(devcontainer_text, docs)

    result = {
        "toolchain_version": parse_toolchain_version(toolchain_text),
        "cargo_rust_version": parse_cargo_rust_version(cargo_text),
        "package_node": parse_node_version_from_package(package_text),
        "pyproject_python": parse_python_version_from_pyproject(pyproject_text),
        "gomod_version": parse_go_version_from_gomod(gomod_text),
        "rust_drifts": rust_drifts_multi,
        "rust_workspace_drifts": rust_workspace_drifts,
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
        "dockerfile_instruction_drifts": dockerfile_instruction_drifts,
        "java_drifts": java_drifts,
        "maven_drifts": maven_drifts,
        "terraform_drifts": terraform_drifts,
        "circleci_drifts": circleci_drifts,
        "gitlab_drifts": gitlab_drifts,
        "helm_drifts": helm_drifts,
        "dc_drifts": dc_drifts,
        "dependabot_drifts": dependabot_drifts,
        "typosquat_drifts": typosquat_drifts,
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
        "bazel_drifts": bazel_drifts,
        "nix_drifts": nix_drifts,
        "poetry_drifts": poetry_drifts,
        "kotlin_drifts": kotlin_drifts,
        "pipfile_drifts": pipfile_drifts,
        "conda_drifts": conda_drifts,
        "gradle_catalog_drifts": gradle_catalog_drifts,
        "kmp_drifts": kmp_drifts,
        "jenkins_drifts": jenkins_drifts,
        "ruby_version_drifts": ruby_version_drifts,
        "python_version_drifts": python_version_drifts,
        "python_version_file_drifts": python_version_file_drifts,
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
        "pre_commit_drifts": pre_commit_drifts,
        "renovate_drifts": find_renovate_drift(root),
    }

    # Run plugin detectors
    plugins = load_plugins(root)
    plugin_results = run_plugin_detectors(root, docs, plugins)
    result.update(plugin_results)

    # Apply excluded detectors filter
    for key in list(result.keys()):
        if key in excluded:
            del result[key]

    # Include skipped symlinks for SARIF suppressed results (issue #128)
    if skipped_symlinks:
        result["_skipped_symlinks"] = skipped_symlinks

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
    # Typosquat
    "find_typosquat_drift",
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
    # Nix
    "find_nix_drift",
    # Devcontainer
    "find_devcontainer_drift",
    # Environment drift
    "find_env_drift_combined",
    # Orchestrator
    "scan_repo",
]
