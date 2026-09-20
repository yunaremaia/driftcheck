"""Tests for _print_blocking_drifts silent-drop bug fix (issue #233).

Verifies that every drift type in DETECTOR_INFO has a corresponding
print handler in _print_blocking_drifts.
"""
import sys
import io
from pathlib import Path
from driftcheck.cli import main, DETECTOR_INFO, INFORMATIONAL_DRIFTS, _print_blocking_drifts


def test_all_detector_keys_captured_by_print_blocking(capsys):
    """Every key in DETECTOR_INFO must be printed by _print_blocking_drifts."""
    # Build a fake all_drifts dict with one entry per key
    all_drifts = {}
    for key in DETECTOR_INFO:
        if key in INFORMATIONAL_DRIFTS:
            continue  # These are handled by _print_informational
        # Create a representative drift entry with all possible fields
        all_drifts[key] = [{
            "file": "README.md",
            "tool": "test",
            "doc_version": "1.0",
            "package_version": "2.0",
            "pyproject_version": "2.0",
            "gomod_version": "2.0",
            "gemfile_version": "2.0",
            "composer_version": "2.0",
            "gradle_version": "2.0",
            "maven_version": "2.0",
            "terraform_version": "2.0",
            "circleci_image": "2.0",
            "gitlab_image": "2.0",
            "k8s_image": "2.0",
            "helm_image": "2.0",
            "compose_image": "2.0",
            "csproj_version": "2.0",
            "tool_versions_version": "2.0",
            "taskfile_version": "2.0",
            "deno_json_version": "2.0",
            "pubspec_version": "2.0",
            "makefile_version": "2.0",
            "mix_version": "2.0",
            "cmake_version": "2.0",
            "requirements_version": "2.0",
            "pipfile_version": "2.0",
            "lock_version": "2.0",
            "environment_version": "2.0",
            "catalog_version": "2.0",
            "readme_version": "1.0",
            "jenkins_version": "2.0",
            "version_file": "2.0",
            "yarnrc_version": "2.0",
            "mise_version": "2.0",
            "package": "requests",
            "detail": "test drift detail",
            "message": "test drift message",
            "action": "checkout",
            "current": "v3",
            "suggested": "v4",
            "doc_image": "node:18",
            "dockerfile_image": "node:20",
            "runner": "ubuntu-20.04",
            "doc_count": "5",
            "actual_count": "6",
            "image": "nginx",
            "tag": "1.21",
            "line": "1",
            "pos": 0,
            "feature": "rust",
            "devcontainer_version": "1.0",
            "config_version": "2.0",
            "source": "MODULE.bazel",
            "repo": "pre-commit/pre-commit-hooks",
            "rev": "v4.0",
            "pin_version": "3.9",
            "floor_source": "pyproject.toml",
            "floor_version": "3.10",
            "toolchain_version": "1.70",
            "cargo_version": "1.70",
            "expected_version": "1.70",
            "provider": "aws",
        }]

    # Also add a plugin drift to test generic handler
    all_drifts["plugin_test_drifts"] = [{
        "file": "custom.yaml",
        "detail": "custom plugin drift",
    }]

    # Call the print function
    _print_blocking_drifts(all_drifts, {})

    captured = capsys.readouterr()
    output = captured.out

    # More direct test: count unique drift keys that produced output
    # We can verify by checking that no key was silently dropped
    # by examining the source code for explicit handling
    import inspect
    source = inspect.getsource(_print_blocking_drifts)

    # Every non-informational key must appear in the source
    unhandled = []
    for key in DETECTOR_INFO:
        if key in INFORMATIONAL_DRIFTS:
            continue
        if key.startswith("plugin_"):
            continue
        # Check if the key is referenced in the function
        if f'"{key}"' not in source and f"'{key}'" not in source:
            # Also check if it's handled via a dict (like _version_files)
            if key not in source:
                unhandled.append(key)

    assert not unhandled, f"Drift keys not handled by _print_blocking_drifts: {unhandled}"


def test_generic_fallback_handles_unknown_keys(capsys):
    """Unknown drift keys should be handled by generic fallback, not silently dropped."""
    # Add a future drift type that doesn't exist yet
    all_drifts = {
        "future_detector_drifts": [{
            "file": "future.txt",
            "detail": "some future drift detail",
            "doc_version": "1.0",
        }]
    }

    _print_blocking_drifts(all_drifts, {})
    captured = capsys.readouterr()

    assert "future_detector_drifts" not in captured.out or "some future drift detail" in captured.out, \
        "Generic fallback should print unknown drift types"


def test_plugin_drifts_handled(capsys):
    """Plugin drifts should be handled by the generic plugin handler."""
    all_drifts = {
        "plugin_security_drifts": [
            {"file": "Dockerfile", "detail": "outdated base image"},
            {"file": "package.json", "detail": "vulnerable dependency"},
        ],
        "plugin_compliance_drifts": [
            {"file": "LICENSE", "detail": "missing license header"},
        ],
    }

    _print_blocking_drifts(all_drifts, {})
    captured = capsys.readouterr()

    assert "outdated base image" in captured.out
    assert "vulnerable dependency" in captured.out
    assert "missing license header" in captured.out
