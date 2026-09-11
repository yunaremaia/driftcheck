"""Driftcheck detectors: version drift detection for various toolchains."""
from .rust import (
    parse_toolchain_version,
    find_rust_drift,
    find_rust_drift_multi,
    parse_cargo_rust_version,
    TOOLCHAIN_RE,
    CARGO_RE,
    DOC_RE,
    DOC_RE_LOOSE,
)
from .node import (
    parse_node_version_from_package,
    find_node_drift,
    NODE_RE,
    ENGINES_RE,
)
from .python import (
    parse_python_version_from_pyproject,
    find_python_drift,
    PY_RE,
)
from .go import (
    parse_go_version_from_gomod,
    find_go_drift,
    GO_RE,
    GO_MOD_RE,
)
from .docker import (
    parse_dockerfile_from,
    find_docker_drift,
    DOCKER_FROM_RE,
    DOCKER_TAG_RE,
)
from .docker_multistage import (
    parse_from_stages,
    find_dockerfile_multistage_drift,
    FROM_RE,
)
from .java import (
    parse_gradle_java_version,
    find_java_drift,
    GRADLE_JAVA_RE,
    GRADLE_KOTLIN_RE,
    JAVA_DOC_RE,
)
from .maven import (
    parse_maven_java_version,
    find_maven_drift,
    MAVEN_VER_RE,
    MAVEN_DOC_RE,
)
from .terraform import (
    parse_terraform_provider_versions,
    find_terraform_drift,
    TERRAFORM_PROVIDER_RE,
    TERRAFORM_VER_RE,
)
from .circleci import (
    parse_circleci_images,
    find_circleci_drift,
    CIRCLECI_IMAGE_RE,
    CIRCLECI_VER_RE,
)
from .gitlab import (
    parse_gitlab_images,
    find_gitlab_drift,
    GITLAB_IMAGE_RE,
    GITLAB_VER_RE,
)
from .actions import (
    find_actions_node_drift,
    find_gh_actions_version_drift,
    ACTIONS_RE,
    GH_ACTIONS_RE,
    GH_ACTIONS_LATEST,
    ACTIONS_NODE24_FIX,
)
from .k8s import (
    parse_k8s_images,
    find_k8s_drift,
    K8S_IMAGE_RE,
    K8S_VER_RE,
)
from .helm import (
    parse_helm_images,
    find_helm_drift,
    HELM_IMAGE_RE,
    HELM_VER_RE,
)
from .compose import (
    parse_docker_compose_images,
    find_docker_compose_drift,
    DC_IMAGE_RE,
    DC_VER_RE,
)
from .dotnet import (
    parse_dotnet_tfm,
    find_dotnet_drift,
    DOTNET_TF_RE,
    DOTNET_DOC_RE,
)
from .ruby import (
    parse_gemfile_ruby_version,
    find_ruby_drift,
    GEMFILE_RUBY_RE,
    RUBY_DOC_RE,
)
from .php import (
    parse_composer_php_version,
    find_php_drift,
    COMPOSER_PHP_RE,
    PHP_DOC_RE,
)
from .bun import (
    parse_bun_version_from_package,
    find_bun_drift,
    BUN_ENGINES_RE,
    BUN_DOC_RE,
)
from .lockfile import find_lockfile_drift
from .deno import (
    parse_deno_version,
    find_deno_drift,
    DENO_JSON_VER_RE,
    DENO_DOC_RE,
)
from .tool_versions import (
    parse_tool_versions,
    find_tool_versions_drift,
    TOOL_VERSION_RE,
)
from .nvmrc import (
    parse_nvmrc_version,
    find_nvmrc_drift,
    NVMRC_RE,
)
from .swift import (
    parse_swift_version_from_package,
    find_swift_drift,
    SPM_VERSION_RE,
    SWIFT_DOC_RE,
)
from .dart import (
    parse_dart_sdk_version,
    find_dart_drift,
    DART_SDK_RE,
    DART_DOC_RE,
)
from .lineending import (
    find_lineending_drift,
    EOL_ATTR_RE,
    EOL_LINE_RE,
)
from .external import (
    find_external_resource_drift,
    EXTERNAL_CDN_RE,
)
from .count import (
    find_count_drift,
    COUNT_RE,
)
from .dependabot import (
    find_dependabot_drift,
    DEPENDABOT_RE,
    ECOSYSTEM_FILES,
)
from .ci_os import (
    find_ci_os_drift,
    CI_OS_DEPRECATED,
    CI_OS_RE,
)
from .makefile import (
    parse_makefile_versions,
    find_makefile_drift,
    MAKEFILE_VERSION_VAR_RE,
    MAKEFILE_TOOL_ASSIGN_RE,
)
from .elixir import (
    parse_mix_elixir_version,
    find_elixir_drift,
    MIX_ELIXIR_RE,
)
from .cmake import (
    parse_cmake_version,
    find_cmake_drift,
    CMAKE_VERSION_RE,
)
from .requirements import (
    parse_requirements_packages,
    find_requirements_drift,
    REQUIREMENTS_PKG_RE,
)
from .kotlin import (
    parse_kotlin_version,
    find_kotlin_drift,
    KOTLIN_PLUGIN_RE,
)
from .env_drift import (
    find_env_drift,
    find_compose_override_drift,
    find_helm_values_drift,
    find_env_drift_combined,
    parse_env_file,
)
from .gradle_catalog import (
    parse_gradle_catalog,
    find_gradle_catalog_drift,
    LIBS_VERSIONS_RE,
)
from .pipfile import (
    parse_pipfile_versions,
    find_pipfile_drift,
    PIPFILE_RE,
    PIPFILE_LOCK_RE,
)
from .conda import (
    parse_conda_environment,
    find_conda_drift,
    CONDA_ENV_RE,
)
from .jenkins import (
    parse_jenkins_node_agent,
    parse_jenkins_nodejs_version,
    parse_jenkins_python_version,
    parse_jenkins_docker_images,
    find_jenkins_drift,
    JENKINS_NODE_RE,
    JENKINS_NODEJS_RE,
    JENKINS_PYTHON_RE,
    JENKINS_DOCKER_IMAGE_RE,
)
from .version_files import (
    parse_ruby_version,
    parse_python_version,
    parse_node_version,
    parse_java_version,
    parse_terraform_version,
    find_version_file_drift,
)
from .npmrc import (
    parse_npmrc,
    find_npmrc_drift,
)
from .yarnrc import (
    parse_yarnrc_version,
    find_yarnrc_drift,
)
from .pnpm import (
    parse_pnpm_workspace,
    find_pnpm_workspace_drift,
)
from .package_manager import (
    parse_package_manager_field,
    detect_lockfile_manager,
    find_package_manager_drift,
)
from .vscode import (
    parse_vscode_extensions,
    find_vscode_extensions_drift,
)
from .git_tag import (
    get_latest_git_tag,
    find_git_tag_drift,
)
from .editorconfig import (
    parse_editorconfig,
    find_editorconfig_drift,
)
from .taskfile import (
    find_taskfile_drift,
    parse_taskfile,
    parse_makefile,
)
from .git_tag import (
    get_latest_git_tag,
    find_git_tag_drift,
)
from .fix import apply_fixes

__all__ = [
    # Rust
    "parse_toolchain_version",
    "find_rust_drift",
    "find_rust_drift_multi",
    "parse_cargo_rust_version",
    "TOOLCHAIN_RE",
    "CARGO_RE",
    "DOC_RE",
    "DOC_RE_LOOSE",
    # Node
    "parse_node_version_from_package",
    "find_node_drift",
    "NODE_RE",
    "ENGINES_RE",
    # Python
    "parse_python_version_from_pyproject",
    "find_python_drift",
    "PY_RE",
    # Go
    "parse_go_version_from_gomod",
    "find_go_drift",
    "GO_RE",
    "GO_MOD_RE",
    # Docker
    "parse_dockerfile_from",
    "find_docker_drift",
    "DOCKER_FROM_RE",
    "DOCKER_TAG_RE",
    # Java
    "parse_gradle_java_version",
    "find_java_drift",
    "GRADLE_JAVA_RE",
    "GRADLE_KOTLIN_RE",
    "JAVA_DOC_RE",
    # Maven
    "parse_maven_java_version",
    "find_maven_drift",
    "MAVEN_VER_RE",
    "MAVEN_DOC_RE",
    # Terraform
    "parse_terraform_provider_versions",
    "find_terraform_drift",
    "TERRAFORM_PROVIDER_RE",
    "TERRAFORM_VER_RE",
    # CircleCI
    "parse_circleci_images",
    "find_circleci_drift",
    "CIRCLECI_IMAGE_RE",
    "CIRCLECI_VER_RE",
    # GitLab
    "parse_gitlab_images",
    "find_gitlab_drift",
    "GITLAB_IMAGE_RE",
    "GITLAB_VER_RE",
    # GitHub Actions
    "find_actions_node_drift",
    "find_gh_actions_version_drift",
    "ACTIONS_RE",
    "GH_ACTIONS_RE",
    "GH_ACTIONS_LATEST",
    "ACTIONS_NODE24_FIX",
    # Kubernetes
    "parse_k8s_images",
    "find_k8s_drift",
    "K8S_IMAGE_RE",
    "K8S_VER_RE",
    # Helm
    "parse_helm_images",
    "find_helm_drift",
    "HELM_IMAGE_RE",
    "HELM_VER_RE",
    # Docker Compose
    "parse_docker_compose_images",
    "find_docker_compose_drift",
    "DC_IMAGE_RE",
    "DC_VER_RE",
    # .NET
    "parse_dotnet_tfm",
    "find_dotnet_drift",
    "DOTNET_TF_RE",
    "DOTNET_DOC_RE",
    # Ruby
    "parse_gemfile_ruby_version",
    "find_ruby_drift",
    "GEMFILE_RUBY_RE",
    "RUBY_DOC_RE",
    # PHP
    "parse_composer_php_version",
    "find_php_drift",
    "COMPOSER_PHP_RE",
    "PHP_DOC_RE",
    # Bun
    "parse_bun_version_from_package",
    "find_bun_drift",
    "BUN_ENGINES_RE",
    "BUN_DOC_RE",
    # Lockfile
    "find_lockfile_drift",
    # Line endings
    "find_lineending_drift",
    "EOL_ATTR_RE",
    "EOL_LINE_RE",
    # External resources
    "find_external_resource_drift",
    "EXTERNAL_CDN_RE",
    # Count
    "find_count_drift",
    "COUNT_RE",
    # Dependabot
    "find_dependabot_drift",
    "DEPENDABOT_RE",
    "ECOSYSTEM_FILES",
    # CI OS
    "find_ci_os_drift",
    "CI_OS_DEPRECATED",
    "CI_OS_RE",
    # Makefile
    "parse_makefile_versions",
    "find_makefile_drift",
    "MAKEFILE_VERSION_VAR_RE",
    "MAKEFILE_TOOL_ASSIGN_RE",
    # Environment drift
    "find_env_drift_combined",
    "parse_env_file",
    # Tool versions
    "TOOL_VERSION_RE",
    # NVMRC
    "NVMRC_RE",
    # Deno
    "parse_deno_version",
    "find_deno_drift",
    # Swift
    "parse_swift_version_from_package",
    "find_swift_drift",
    "SPM_VERSION_RE",
    "SWIFT_DOC_RE",
    # Dart
    "parse_dart_sdk_version",
    "find_dart_drift",
    "DART_SDK_RE",
    "DART_DOC_RE",
    # Requirements
    "parse_requirements_packages",
    "find_requirements_drift",
    "REQUIREMENTS_PKG_RE",
    # Kotlin
    "parse_kotlin_version",
    "find_kotlin_drift",
    "KOTLIN_PLUGIN_RE",
    # Gradle Version Catalog
    "parse_gradle_catalog",
    "find_gradle_catalog_drift",
    "LIBS_VERSIONS_RE",
    # Pipfile
    "parse_pipfile_versions",
    "find_pipfile_drift",
    "PIPFILE_RE",
    "PIPFILE_LOCK_RE",
    # Conda
    "parse_conda_environment",
    "find_conda_drift",
    "CONDA_ENV_RE",
    # Fix
    "apply_fixes",
]
