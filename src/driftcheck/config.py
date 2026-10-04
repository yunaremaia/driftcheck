"""Configuration loading for driftcheck.

Reads .driftcheck.toml from repo root to customize detection behavior.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

try:  # Python 3.11+ stdlib
    import tomllib
except ImportError:  # Python 3.10 backport (declared in pyproject.toml)
    import tomli as tomllib  # type: ignore[no-redef]

# All drift type keys — shared across CLI modes
DRIFT_KEYS = [
    "rust_drifts", "node_drifts", "bun_drifts", "package_version_drifts", "python_drifts", "python_setup_drifts", "go_drifts",
    "count_drifts", "actions_drifts", "lineending_drifts", "docker_drifts", "docker_multistage_drifts", "docker_bases_drifts",
    "java_drifts", "maven_drifts", "terraform_drifts", "circleci_drifts",
    "renovate_drifts", "gh_actions_version_drifts", "k8s_drifts", "helm_drifts", "git_submodule_drifts",
    "rust_workspace_drifts",
    "dc_drifts", "ci_os_drifts", "dotnet_drifts", "ruby_drifts", "php_drifts",
    "env_drifts",
    "env_example_drifts",
    "compose_override_drifts",
    "helm_values_drifts",
    "external_resource_drifts", "dependabot_drifts",
    "lockfile_drifts", "package_lock_drifts", "tool_versions_drifts", "nvmrc_drifts",
    "engines_drifts",
    "swift_drifts", "deno_drifts", "dart_drifts", "makefile_drifts",
    "elixir_drifts", "cmake_drifts", "requirements_drifts", "kotlin_drifts",
    "pipfile_drifts", "conda_drifts", "gradle_catalog_drifts", "jenkins_drifts",
    "ruby_version_drifts", "python_version_drifts", "node_version_drifts",
    "java_version_drifts", "terraform_version_drifts",
    "npmrc_drifts", "yarnrc_drifts", "pnpm_workspace_drifts", "package_manager_drifts",
    "vscode_ext_drifts", "editorconfig_drifts", "git_tag_drifts", "devcontainer_drifts",
    "taskfile_drifts", "mise_drifts",
    "pre_commit_drifts",
    "changelog_drifts",
    "typosquat_drifts",
    "cargo_feature_drifts",
    "poetry_drifts",
    "npm_workspace_drifts",
    "julia_drifts",
    "bazel_drifts",
    "nix_drifts",
    # Keys emitted by scan_repo that were previously absent from this list.
    # DRIFT_KEYS is the exit-code gate (cli.py builds `all_drifts` from it), so
    # a key missing here was detected, serialised into --json, written to --csv
    # and reported by --sarif at level=error -- while the process still exited 0.
    "a2a_drifts",
    "dockerfile_instruction_drifts",
    "freshness_drifts",
    "frontmatter_drifts",
    "gitlab_drifts",
    "go_replace_drifts",
    "helm_dependency_drifts",
    "justfile_drifts",
    "kmp_drifts",
    "pyproject_tool_drifts",
    "python_req_drifts",
    "python_version_file_drifts",
    "r_drifts",
    "scala_drifts",
    "terraform_lock_drifts",
    # Emitted by find_uv_lock_drift, which was shipped but never called from
    # detector.py, so uv.lock-vs-pyproject.toml mismatches were reported
    # nowhere -- not in --json, not in --sarif, and not in the exit code.
    "uv_lock_drifts",
]

# Drift types that are reported but never fail the check.
#
# This lives here, in the leaf module, because it used to be duplicated as
# `INFORMATIONAL_DRIFTS` (cli.py) and `INFORMATIONAL_TYPES` (sarif.py). The two
# copies had drifted apart: `changelog_drifts` and `typosquat_drifts` were
# non-blocking for the exit code while SARIF still emitted them at
# `level=error`, so `typosquat_drifts` opened a blocking Code Scanning alert
# while the process exited 0. Severity has to be one fact, so both consumers
# read it from here.
#
# `freshness_drifts` is included deliberately: it is the only detector whose
# verdict comes from outside the repository. `find_python_dep_freshness`
# queries live PyPI, so the same tree yields a different answer depending on
# network reachability and on what was published upstream that day. A blocking
# gate must be a property of the repo under test; this one is a property of the
# internet.
INFORMATIONAL_DRIFT_KEYS = {
    "external_resource_drifts",
    "dependabot_drifts",
    "lockfile_drifts",
    "nvmrc_drifts",
    "typosquat_drifts",
    "changelog_drifts",
    "freshness_drifts",
}

# Default configuration
DEFAULT_CONFIG = {
    "exclude_detectors": [],
    "ignore_patterns": [],
    "fail_on_informational": False,
    "doc_paths": None,  # None = auto-detect README.md, CONTRIBUTING.md, docs/README*.md
    "custom_detectors": [],
    "follow_symlinks": True,  # If False, skip symlinks outside repo root during scan
    "max_file_size": 1_000_000,  # 1MB default — files larger than this are skipped (OOM protection)
}


def _parse_toml(text: str) -> dict[str, Any]:
    """Parse TOML with the stdlib `tomllib` (or the `tomli` backport on 3.10).

    The previous hand-rolled line splitter mis-handled inline comments,
    multi-line arrays and `#` inside quoted strings (issue #143), silently
    turning a list into a string. `tomllib` is a full TOML v1.0.0 parser, so
    those constructs now behave as written; malformed TOML raises
    `tomllib.TOMLDecodeError` instead of yielding a half-parsed dict.
    """
    return tomllib.loads(text)


def load_config(root: Path = Path(".")) -> dict[str, Any]:
    """Load .driftcheck.toml from repo root, return merged config."""
    cfg = dict(DEFAULT_CONFIG)
    toml_path = root / ".driftcheck.toml"
    if toml_path.exists():
        text = toml_path.read_text(encoding="utf-8")
        raw = _parse_toml(text)
        # Flatten: [driftcheck] section takes top-level precedence.
        #
        # Top-level keys are applied first and [driftcheck] second, so the
        # section still wins. The previous `if k not in cfg` guard was meant to
        # express that precedence, but `cfg` is pre-seeded from
        # DEFAULT_CONFIG, so the condition was False for every key that has a
        # default: a top-level `exclude_detectors = ["node"]` was dropped on the
        # floor while the same key under [driftcheck] worked. That is a silent
        # misconfiguration — the user excludes a detector and driftcheck keeps
        # reporting the drift anyway — so the default must be overridable.
        for k, v in raw.items():
            # A foreign table such as [tool.foo] or [something-else] parses as a
            # dict; it is not driftcheck config and must not land in cfg.
            if k != "driftcheck" and not isinstance(v, dict):
                cfg[k] = v
        if "driftcheck" in raw:
            for k, v in raw["driftcheck"].items():
                cfg[k] = v
    return cfg


def get_excluded_detectors(config: dict[str, Any]) -> set[str]:
    """Get set of detector keys to exclude based on config."""
    excluded = set()
    for key in config.get("exclude_detectors", []):
        # Support both short names (e.g., "node") and drift keys (e.g., "node_drifts")
        if not key.endswith("_drifts"):
            # Map special short names to actual drift keys
            if key == "rust":
                excluded.add("rust_drifts")
            else:
                excluded.add(f"{key}_drifts")
        else:
            excluded.add(key)
    return excluded


def get_custom_detectors(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Get list of custom detector definitions from config."""
    return config.get("custom_detectors", [])
