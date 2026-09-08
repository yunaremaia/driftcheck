"""Configuration loading for driftcheck.

Reads .driftcheck.toml from repo root to customize detection behavior.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

# All drift type keys — shared across CLI modes
DRIFT_KEYS = [
    "drifts", "rust_drifts", "node_drifts", "bun_drifts", "python_drifts", "go_drifts",
    "count_drifts", "actions_drifts", "lineending_drifts", "docker_drifts",
    "java_drifts", "maven_drifts", "terraform_drifts", "circleci_drifts",
    "gitlab_drifts", "gh_actions_version_drifts", "k8s_drifts", "helm_drifts",
    "dc_drifts", "ci_os_drifts", "dotnet_drifts", "ruby_drifts", "php_drifts",
    "env_drifts",
    "external_resource_drifts", "dependabot_drifts",
    "lockfile_drifts", "tool_versions_drifts", "nvmrc_drifts",
    "swift_drifts", "deno_drifts", "dart_drifts", "makefile_drifts",
    "elixir_drifts", "cmake_drifts", "requirements_drifts", "kotlin_drifts",
    "pipfile_drifts", "conda_drifts", "gradle_catalog_drifts", "jenkins_drifts",
    "ruby_version_drifts", "python_version_drifts", "node_version_drifts",
    "java_version_drifts", "terraform_version_drifts",
]

# Default configuration
DEFAULT_CONFIG = {
    "exclude_detectors": [],
    "ignore_patterns": [],
    "fail_on_informational": False,
    "doc_paths": None,  # None = auto-detect README.md, CONTRIBUTING.md, docs/README*.md
    "custom_detectors": [],
}


def _parse_toml(text: str) -> dict[str, Any]:
    """Minimal TOML parser for the subset we need (no dependency on tomli)."""
    config: dict[str, Any] = {}
    current_section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            if current_section not in config:
                config[current_section] = {}
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Try to parse as list
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if inner:
                    items = [v.strip().strip('"').strip("'") for v in inner.split(",")]
                else:
                    items = []
                parsed: Any = items
            elif value.lower() == "true":
                parsed = True
            elif value.lower() == "false":
                parsed = False
            else:
                try:
                    parsed = int(value)
                except ValueError:
                    try:
                        parsed = float(value)
                    except ValueError:
                        parsed = value
            if current_section:
                config[current_section][key] = parsed
            else:
                config[key] = parsed
    return config


def load_config(root: Path = Path(".")) -> dict[str, Any]:
    """Load .driftcheck.toml from repo root, return merged config."""
    cfg = dict(DEFAULT_CONFIG)
    toml_path = root / ".driftcheck.toml"
    if toml_path.exists():
        text = toml_path.read_text(encoding="utf-8")
        raw = _parse_toml(text)
        # Flatten: [driftcheck] section takes top-level precedence
        if "driftcheck" in raw:
            for k, v in raw["driftcheck"].items():
                cfg[k] = v
        for k, v in raw.items():
            if k != "driftcheck" and k not in cfg:
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
                excluded.add("drifts")
                excluded.add("rust_drifts")
            else:
                excluded.add(f"{key}_drifts")
        else:
            excluded.add(key)
    return excluded
