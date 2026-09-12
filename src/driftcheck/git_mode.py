"""Git-mode scanning: only check files changed since a base commit.

Enables fast incremental drift detection in CI by scanning only files
that changed relative to a base commit (default: HEAD~1).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def get_changed_files(root: Path, base_commit: str = "HEAD~1") -> set[str]:
    """Get set of file paths changed since base_commit.
    
    Returns relative paths from repo root. Falls back to all files
    if git is not available or base_commit doesn't exist.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_commit, "--"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return set()
        files = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()


def get_changed_and_untracked(root: Path, base_commit: str = "HEAD~1") -> set[str]:
    """Get changed files plus untracked files (for full PR coverage)."""
    changed = get_changed_files(root, base_commit)
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            untracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
            changed.update(untracked)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return changed


def filter_detectors_by_files(
    changed_files: set[str],
    detector_file_patterns: dict[str, list[str]],
) -> set[str]:
    """Filter detectors to only those whose relevant files changed.
    
    Args:
        changed_files: set of relative file paths that changed
        detector_file_patterns: mapping of detector key to glob patterns
            for files that detector cares about
    
    Returns:
        set of detector keys that should run
    """
    if not changed_files:
        return set(detector_file_patterns.keys())
    
    relevant = set()
    for detector_key, patterns in detector_file_patterns.items():
        for pattern in patterns:
            # Simple glob matching for changed files
            for f in changed_files:
                if _glob_match(f, pattern):
                    relevant.add(detector_key)
                    break
            if detector_key in relevant:
                break
    
    # Always include doc-related detectors if any doc file changed
    doc_changed = any(
        f.endswith((".md", ".rst", ".txt")) or "README" in f or "CONTRIBUTING" in f
        for f in changed_files
    )
    if doc_changed:
        # All detectors that compare against docs are potentially relevant
        for key in detector_file_patterns:
            if key != "env_drifts":  # env drifts don't compare against docs
                relevant.add(key)
    
    return relevant


def _glob_match(path: str, pattern: str) -> bool:
    """Simple glob matching (supports * and ** wildcards)."""
    import fnmatch
    # Handle **/ prefix
    if pattern.startswith("**/"):
        # Match any suffix
        suffix = pattern[3:]
        if fnmatch.fnmatch(path, suffix):
            return True
        # Match any path ending with suffix
        parts = path.split("/")
        for i in range(len(parts)):
            subpath = "/".join(parts[i:])
            if fnmatch.fnmatch(subpath, suffix):
                return True
        return False
    return fnmatch.fnmatch(path, pattern)


# Mapping of detector keys to the file patterns they care about.
# Used to skip detectors whose relevant files haven't changed.
DETECTOR_FILE_PATTERNS: dict[str, list[str]] = {
    "drifts": ["rust-toolchain.toml", "README.md", "CONTRIBUTING.md", "docs/README*.md"],
    "rust_drifts": ["rust-toolchain.toml", "Cargo.toml", "README.md", "CONTRIBUTING.md"],
    "node_drifts": ["package.json", "README.md", "CONTRIBUTING.md"],
    "bun_drifts": ["package.json", "README.md", "CONTRIBUTING.md"],
    "python_drifts": ["pyproject.toml", "README.md", "CONTRIBUTING.md"],
    "go_drifts": ["go.mod", "README.md", "CONTRIBUTING.md"],
    "docker_drifts": ["Dockerfile", "Dockerfile.*", "docker/Dockerfile*", "README.md"],
    "java_drifts": ["build.gradle", "build.gradle.kts", "README.md"],
    "maven_drifts": ["pom.xml", "README.md"],
    "terraform_drifts": ["versions.tf", "*.tf", "terraform/*.tf", "README.md"],
    "circleci_drifts": [".circleci/config.yml", "README.md"],
    "gitlab_drifts": [".gitlab-ci.yml", "README.md"],
    "k8s_drifts": ["k8s/**/*.yaml", "k8s/**/*.yml", "deploy/**/*.yaml", "deploy/**/*.yml", "README.md"],
    "helm_drifts": ["Chart.yaml", "charts/**/Chart.yaml", "values.yaml", "README.md"],
    "dc_drifts": ["docker-compose.yml", "docker-compose.yaml", "docker-compose.*.yml", "docker-compose.*.yaml", "compose.yml", "compose.yaml", "docker/docker-compose.yml"],
    "dotnet_drifts": ["*.csproj", "**/*.csproj", "README.md"],
    "ruby_drifts": ["Gemfile", "README.md"],
    "php_drifts": ["composer.json", "README.md"],
    "env_drifts": [".env", ".env.example", "docker-compose*.yml", "docker-compose*.yaml", "values*.yaml"],
    "env_example_drifts": [".env", ".env.example"],
    "compose_override_drifts": ["docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml"],
    "helm_values_drifts": ["values*.yaml", "values*.yml", "charts/**/values*.yaml"],
    "actions_drifts": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "gh_actions_version_drifts": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "ci_os_drifts": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "lineending_drifts": [".gitattributes", "*.py", "*.js", "*.ts", "*.rs", "*.go", "*.java"],
    "count_drifts": ["skills/**", "README.md"],
    "external_resource_drift": ["*.html", "*.md"],

    "dependabot_drifts": [".github/dependabot.yml", "package.json", "Cargo.toml", "go.mod", "Gemfile"],
    "typosquat_drifts": ["requirements.txt", "pyproject.toml", "Pipfile", "package.json", "Cargo.toml"],

    "lockfile_drifts": ["package-lock.json", "yarn.lock", "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock", "poetry.lock", "uv.lock"],
    "engines_drifts": ["package.json", ".nvmrc"],
    "tool_versions_drifts": [".tool-versions", "README.md"],
    "nvmrc_drifts": [".nvmrc", "package.json", "README.md"],
    "swift_drifts": ["Package.swift", "README.md"],
    "deno_drifts": ["deno.json", "deno.jsonc", "README.md"],
    "dart_drifts": ["pubspec.yaml", "README.md"],
    "makefile_drifts": ["Makefile", "makefile", "GNUmakefile", "Makefile.*", "make/*.mk", "README.md"],
    "elixir_drifts": ["mix.exs", "README.md"],
    "cmake_drifts": ["CMakeLists.txt", "cmake/CMakeLists.txt", "src/CMakeLists.txt", "README.md"],
    "jenkins_drifts": ["Jenkinsfile", "jenkins/Jenkinsfile", "jenkinsfile", "Jenkinsfile.*", "README.md"],
    "ruby_version_drifts": [".ruby-version", "README.md"],
    "python_version_drifts": [".python-version", "README.md"],
    "node_version_drifts": [".node-version", "README.md"],
    "java_version_drifts": [".java-version", "README.md"],
    "terraform_version_drifts": [".terraform-version", "README.md"],
    "npmrc_drifts": [".npmrc", "README.md"],
    "yarnrc_drifts": [".yarnrc.yml", "README.md"],
    "pnpm_workspace_drifts": ["pnpm-workspace.yaml", "package.json", "README.md"],
    "package_manager_drifts": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
    "vscode_ext_drifts": [".vscode/extensions.json", "README.md"],
    "editorconfig_drifts": [".editorconfig", ".vscode/settings.json", "README.md"],
    "taskfile_drifts": ["Taskfile.yml", "Taskfile.yaml", "Makefile"],
    "devcontainer_drifts": [".devcontainer/devcontainer.json", ".devcontainer/*.devcontainer.json", "devcontainer.json", "README.md"],
    "mise_drifts": ["mise.toml", "README.md"],
}
