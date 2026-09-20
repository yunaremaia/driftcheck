"""Configuration loading for driftcheck.

Reads .driftcheck.toml from repo root to customize detection behavior.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any

# All drift type keys — shared across CLI modes
DRIFT_KEYS = [
    "rust_drifts", "node_drifts", "bun_drifts", "python_drifts", "go_drifts",
    "count_drifts", "actions_drifts", "lineending_drifts", "docker_drifts", "docker_multistage_drifts", "docker_bases_drifts",
    "java_drifts", "maven_drifts", "terraform_drifts", "circleci_drifts",
    "gitlab_drifts", "gh_actions_version_drifts", "k8s_drifts", "helm_drifts",
    "dc_drifts", "ci_os_drifts", "dotnet_drifts", "ruby_drifts", "php_drifts",
    "env_drifts",
    "env_example_drifts",
    "compose_override_drifts",
    "helm_values_drifts",
    "external_resource_drifts", "dependabot_drifts",
    "lockfile_drifts", "tool_versions_drifts", "nvmrc_drifts",
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
    "typosquat_drifts",
    "poetry_drifts",
    "renovate_drifts",
    "bazel_drifts",
    "nix_drifts",
    "rust_workspace_drifts",
]

# Default configuration
DEFAULT_CONFIG = {
    "exclude_detectors": [],
    "ignore_patterns": [],
    "fail_on_informational": False,
    "doc_paths": None,  # None = auto-detect README.md, CONTRIBUTING.md, docs/README*.md
    "custom_detectors": [],
    "follow_symlinks": True,  # If False, skip symlinks outside repo root during scan
    "max_file_size": 1_000_000,  # 1MB default — files larger than this are skipped (OOM protection)
    # Parallel read timeouts (issue #238)
    "read_timeout": 5,      # per-file future.result() timeout in seconds
    "read_pool_timeout": 30,  # as_completed() pool-wide timeout in seconds
}


def _parse_toml(text: str) -> dict[str, Any]:
    """Parse TOML config from text using the standard library (tomllib/tomli)."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    return tomllib.loads(text)


def _coerce_bool(value: Any, default: Any) -> bool:
    """Coerce string/boolean/int to boolean.

    TOML's tomllib strictly types values — a user writing
    ``follow_symlinks = "false"`` (quoted) gets a *string* "false",
    which is truthy in Python. This helper normalizes common
    truthy/falsy strings so config intent is preserved.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("false", "no", "0", ""):
            return False
        if value.lower() in ("true", "yes", "1"):
            return True
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def validate_config(raw: dict[str, Any], strict: bool = False) -> list[str]:
    """Validate config keys and value types against the known schema.

    Args:
        raw: Parsed TOML dict (either top-level or from [driftcheck] section).
        strict: If True, raise ConfigValidationError on unknown keys.
               If False, return warnings for unknown keys.

    Returns:
        List of warning messages (empty if valid).

    Raises:
        ConfigValidationError: If strict=True and unknown keys are found.
    """
    warnings = []
    # Known config keys
    valid_keys = set(DEFAULT_CONFIG.keys()) | {"driftcheck"}

    # Validate [driftcheck] section keys too
    sections_to_validate = [raw]
    if "driftcheck" in raw and isinstance(raw["driftcheck"], dict):
        sections_to_validate.append(raw["driftcheck"])

    for section in sections_to_validate:
        for key in section:
            if key not in valid_keys:
                msg = f"Unknown config key: {key!r} (valid keys: {sorted(valid_keys)})"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)

        # Type validation for known keys
        bool_keys = {"fail_on_informational", "follow_symlinks"}
        int_keys = {"max_file_size"}
        num_keys = {"read_timeout", "read_pool_timeout"}  # accept int or float
        list_keys = {"exclude_detectors", "ignore_patterns", "custom_detectors"}

        for key in bool_keys & set(section):
            if not isinstance(section[key], (bool, str, int)):
                msg = f"Invalid type for {key!r}: expected bool, got {type(section[key]).__name__}"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)

        for key in int_keys & set(section):
            if not isinstance(section[key], int):
                msg = f"Invalid type for {key!r}: expected int, got {type(section[key]).__name__}"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)

        for key in num_keys & set(section):
            if not isinstance(section[key], (int, float)):
                msg = f"Invalid type for {key!r}: expected int or float, got {type(section[key]).__name__}"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)
            elif section[key] <= 0:
                msg = f"Invalid value for {key!r}: must be > 0, got {section[key]!r}"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)

        for key in list_keys & set(section):
            if section[key] is not None and not isinstance(section[key], list):
                msg = f"Invalid type for {key!r}: expected list, got {type(section[key]).__name__}"
                if strict:
                    raise ConfigValidationError(msg)
                warnings.append(msg)

    return warnings


class ConfigValidationError(Exception):
    """Raised when config validation fails in strict mode."""
    pass


def load_config(root: Path = Path("."), strict: bool = False) -> dict[str, Any]:
    """Load .driftcheck.toml from repo root, return merged config.

    Args:
        root: Repo root path.
        strict: If True, raise ConfigValidationError on unknown keys.
               If False, print warnings to stderr for unknown keys.
    """
    cfg = dict(DEFAULT_CONFIG)
    toml_path = root / ".driftcheck.toml"
    if toml_path.exists():
        text = toml_path.read_text(encoding="utf-8")
        raw = _parse_toml(text)
        # Validate raw config
        warnings = validate_config(raw, strict=strict)
        if warnings and not strict:
            for w in warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        # Flatten: [driftcheck] section takes top-level precedence
        if "driftcheck" in raw:
            for k, v in raw["driftcheck"].items():
                cfg[k] = v
        for k, v in raw.items():
            if k != "driftcheck" and k not in cfg:
                cfg[k] = v
    # Coerce follow_symlinks so string "false" doesn't become True
    cfg["follow_symlinks"] = _coerce_bool(cfg.get("follow_symlinks"), DEFAULT_CONFIG["follow_symlinks"])
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


def get_custom_detectors(config: dict[str, Any]) -> list[str]:
    """Get list of custom detector file paths from config."""
    return config.get("custom_detectors", [])


def get_ignore_patterns(config: dict[str, Any]) -> list[str]:
    """Get list of file glob patterns to ignore during scanning.

    Patterns use fnmatch syntax (e.g., ``*.log``, ``node_modules/*``, ``docs/**/*.md``).
    Files matching any pattern are excluded from walked_files before detectors run.
    """
    return config.get("ignore_patterns", [])


def get_read_timeouts(config: dict[str, Any]) -> tuple[float, float]:
    """Return ``(read_timeout, read_pool_timeout)`` from config.

    Both values fall back to their defaults from :data:`DEFAULT_CONFIG` if
    absent or invalid.  This is the canonical way for callers to retrieve
    timeout values — prefer this over direct ``config.get(...)`` calls.

    Args:
        config: Merged config dict as returned by :func:`load_config`.

    Returns:
        A 2-tuple ``(per_file_timeout_seconds, pool_wide_timeout_seconds)``.
    """
    read_timeout = config.get("read_timeout", DEFAULT_CONFIG["read_timeout"])
    read_pool_timeout = config.get("read_pool_timeout", DEFAULT_CONFIG["read_pool_timeout"])
    # Guard against bad values slipping through (e.g. None written in TOML)
    if not isinstance(read_timeout, (int, float)) or read_timeout <= 0:
        read_timeout = DEFAULT_CONFIG["read_timeout"]
    if not isinstance(read_pool_timeout, (int, float)) or read_pool_timeout <= 0:
        read_pool_timeout = DEFAULT_CONFIG["read_pool_timeout"]
    return float(read_timeout), float(read_pool_timeout)


def _matches_ignore_patterns(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any ignore pattern (fnmatch syntax)."""
    import fnmatch
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # Also match against basename for simple patterns
        if fnmatch.fnmatch(Path(rel_path).name, pattern):
            return True
    return False
