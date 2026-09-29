"""Explain driftcheck drift findings in detail.

Provides the --explain CLI command that explains why a specific drift
was detected, showing file, line, values, diff, impact, and suggested fix.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any


# Detector-level impact descriptions — keyed by drift type
IMPACT_DESCRIPTIONS: dict[str, str] = {
    "rust_drifts": "Contributors using the documented Rust version will get compile errors or CI failures because the toolchain requires a different version.",
    "node_drifts": "Contributors using the documented Node.js version will encounter runtime/CI mismatches with the declared engines range.",
    "bun_drifts": "Contributors using the documented Bun version will encounter runtime mismatches with package.json engines.bun.",
    "python_drifts": "Contributors using the documented Python version may hit install failures or CI mismatches with the declared requires-python floor.",
    "python_setup_drifts": "Documentation lists a different package version than setup.py/setup.cfg — contributors and pip installs will see conflicting metadata.",
    "go_drifts": "Contributors using the documented Go version may encounter compile errors or CI mismatches with the go.mod directive.",
    "count_drifts": "README lists a different skill count than the actual skills/ directory — users see stale documentation.",
    "actions_drifts": "GitHub Actions still uses Node 20 which is deprecated — workflows will fail after GitHub removes the runner.",
    "gh_actions_version_drifts": "GitHub Actions uses outdated versions that may break or lose security patches.",
    "lineending_drifts": "Missing .gitattributes leads to inconsistent line endings across platforms — causes noisy diffs and CI failures.",
    "docker_drifts": "Documentation references a different Docker base image than the actual Dockerfile — users pull the wrong image.",
    "docker_multistage_drifts": "Multi-stage Dockerfile has inconsistent base image tags across stages — leads to subtle runtime mismatches.",
    "docker_bases_drifts": "Floating or unpinned Docker base tags — images can change underneath, breaking reproducibility.",
    "java_drifts": "Documentation shows a different Java version than build.gradle sourceCompatibility.",
    "maven_drifts": "Documentation shows a different Java version than pom.xml java.version.",
    "terraform_drifts": "Documentation shows a different provider version than versions.tf.",
    "circleci_drifts": "Documentation references a different CircleCI image than .circleci/config.yml.",
    "gitlab_drifts": "Documentation references a different GitLab CI image than .gitlab-ci.yml.",
    "k8s_drifts": "Documentation references a different container image than Kubernetes manifests.",
    "helm_drifts": "Documentation references a different Helm chart version than Chart.yaml/values.yaml.",
    "dc_drifts": "Documentation references a different Docker Compose image than docker-compose.yml.",
    "ci_os_drifts": "CI uses a deprecated GitHub Actions runner that will be removed.",
    "dotnet_drifts": "Documentation shows a different .NET version than the .csproj TargetFramework.",
    "ruby_drifts": "Documentation shows a different Ruby version than Gemfile.",
    "php_drifts": "Documentation shows a different PHP version than composer.json require.php.",
    "tool_versions_drifts": "Documentation shows a different tool version than .tool-versions.",
    "taskfile_drifts": "Documentation shows a different tool version than Taskfile.yml.",
    "swift_drifts": "Documentation shows a different Swift package version than Package.swift.",
    "deno_drifts": "Documentation shows a different Deno version than deno.json.",
    "dart_drifts": "Documentation shows a different Dart SDK constraint than pubspec.yaml.",
    "makefile_drifts": "Documentation shows a different tool version than the Makefile pin.",
    "elixir_drifts": "Documentation shows a different Elixir version than mix.exs.",
    "cmake_drifts": "Documentation shows a different CMake version than CMakeLists.txt.",
    "requirements_drifts": "Documentation lists a different package version than requirements.txt.",
    "r_drifts": "README R package versions disagree with DESCRIPTION or renv.lock.",
    "kotlin_drifts": "Documentation shows a different Kotlin plugin version than build.gradle.kts.",
    "pipfile_drifts": "Pipfile and Pipfile.lock have version mismatches — installs are not reproducible.",
    "conda_drifts": "Conda environment.yml has unpinned package versions — environments are not reproducible.",
    "gradle_catalog_drifts": "Documentation shows a different version than the Gradle Version Catalog (libs.versions.toml).",
    "npmrc_drifts": "npm registry or settings in .npmrc conflict with package.json — installs may fail or pull from wrong registry.",
    "yarnrc_drifts": "Documentation shows a different Yarn version than .yarnrc.yml.",
    "pnpm_workspace_drifts": "pnpm-workspace.yaml conflicts with package.json workspaces — monorepo resolution fails.",
    "package_manager_drifts": "packageManager field doesn't match the lockfile — wrong package manager used in CI.",
    "vscode_ext_drifts": "VSCode extensions.json doesn't match README recommendations — team uses different tooling.",
    "editorconfig_drifts": ".editorconfig settings don't match README indent/style — inconsistent formatting across editors.",
    "git_tag_drifts": "Latest git tag doesn't match README version mentions — users see stale version badges.",
    "devcontainer_drifts": "Devcontainer.json features/base image don't match README — codespace builds diverge.",
    "pre_commit_drifts": "Pre-commit hook versions don't match .pre-commit-config.yaml — local hooks diverge from CI.",
    "typosquat_drifts": "Dependency list contains potential typosquats — supply chain risk.",
    "external_resource_drifts": "HTML references external CDN resources — privacy and availability concern.",
    "dependabot_drifts": "Dependabot doesn't cover all ecosystems used — some dependencies go unmaintained.",
    "lockfile_drifts": "Lockfile is missing, stale, or orphaned — installs are not reproducible.",
    "nvmrc_drifts": ".nvmrc doesn't match package.json engines — developers use wrong Node version.",
    "engines_drifts": "package.json engines field conflicts with .npmrc engine-strict — installs fail silently.",
    "env_drifts": "Environment config (.env.example vs .env) has key drift — apps fail to start.",
    "env_example_drifts": ".env.example doesn't match .env — developers miss required variables.",
    "compose_override_drifts": "Docker Compose override file has different image than base — production deployments diverge.",
    "helm_values_drifts": "Helm values.yaml has environment-specific values that diverge from defaults — deployments are inconsistent.",
    "package_lock_drifts": "package-lock.json resolutions conflict with package.json ranges — installs may pull wrong versions.",
    "ruby_version_drifts": ".ruby-version doesn't match README — rbenv/rvm users get wrong Ruby.",
    "python_version_drifts": ".python-version doesn't match README — pyenv users get wrong Python.",
    "python_version_file_drifts": ".python-version is below pyproject.toml requires-python floor — code won't run.",
    "node_version_drifts": ".node-version doesn't match README — nvm users get wrong Node.",
    "java_version_drifts": ".java-version doesn't match README — jenv users get wrong Java.",
    "terraform_version_drifts": ".terraform-version doesn't match README — tfenv users get wrong Terraform.",
}


class Explainer:
    """Explain a driftcheck drift finding with full context."""

    def __init__(self, root: Path):
        self.root = root

    def explain(self, drift: dict, drift_type: str) -> dict:
        """Generate a detailed explanation for a single drift.

        Args:
            drift: a drift dict from scan_repo() results
            drift_type: the detector key (e.g., "rust_drifts")

        Returns:
            dict with: drift_type, file, line, actual, expected, diff, impact, fix
        """
        file_path = drift.get("file", "")
        actual = self._extract_actual(drift)
        expected = self._extract_expected(drift)
        line = self._find_line(file_path, actual) if file_path else None
        diff = self._make_diff(actual, expected)
        impact = IMPACT_DESCRIPTIONS.get(drift_type, "Version mismatch between documentation and toolchain.")
        fix = self._suggest_fix(file_path, line, actual, expected)

        return {
            "drift": drift_type,
            "file": file_path,
            "line": line,
            "actual": actual,
            "expected": expected,
            "diff": diff,
            "impact": impact,
            "fix": fix,
        }

    def explain_all(self, results: dict) -> list[dict]:
        """Explain all drifts in a scan_repo() results dict.

        Args:
            results: the dict returned by scan_repo()

        Returns:
            list of explanation dicts (one per drift finding)
        """
        explanations = []
        for drift_type, drifts in results.items():
            if not isinstance(drifts, list) or not drifts:
                continue
            if drift_type in ("toolchain_version", "cargo_rust_version", "package_node",
                              "pyproject_python", "gomod_version"):
                continue
            for drift in drifts:
                if isinstance(drift, dict):
                    explanations.append(self.explain(drift, drift_type))
        return explanations

    def explain_json(self, drift: dict, drift_type: str) -> dict:
        """Alias for explain() — returns JSON-serializable dict."""
        return self.explain(drift, drift_type)

    def explain_text(self, drift: dict, drift_type: str) -> str:
        """Return a human-readable text explanation."""
        e = self.explain(drift, drift_type)
        lines = [
            f"Drift: {e['drift']}",
            f"File: {e['file']}" + (f" (line {e['line']})" if e['line'] else ""),
            f"Actual: {e['actual']}",
            f"Expected: {e['expected']}",
            f"Diff: {e['diff']}",
            f"Impact: {e['impact']}",
            f"Fix: {e['fix']}",
        ]
        return "\n".join(lines)

    def explain_fix(self, drift: dict, drift_type: str) -> str | None:
        """Apply the suggested fix to the file.

        Returns the path of the fixed file, or None if no fix was applied.
        """
        file_path = drift.get("file", "")
        if not file_path:
            return None

        actual = self._extract_actual(drift)
        expected = self._extract_expected(drift)
        if not actual or not expected:
            return None

        full_path = self.root / file_path
        if not full_path.exists():
            return None

        content = full_path.read_text(encoding="utf-8")
        # Only fix documentation files (never toolchain files)
        if full_path.name in ("rust-toolchain.toml", "Cargo.toml", "package.json",
                              "pyproject.toml", "go.mod", "build.gradle", "pom.xml"):
            return None

        new_content = content.replace(actual, expected, 1)
        if new_content != content:
            full_path.write_text(new_content, encoding="utf-8")
            return file_path
        return None

    def _extract_actual(self, drift: dict) -> str:
        """Extract the actual (documented) value from a drift."""
        if drift.get("tool") and drift.get("doc_version"):
            return f"{drift['tool']} {drift['doc_version']}"
        return drift.get("doc_version", drift.get("doc_image", ""))

    def _extract_expected(self, drift: dict) -> str:
        """Extract the expected (toolchain) value from a drift."""
        return (
            drift.get("suggested")
            or drift.get("toolchain_version")
            or drift.get("package_version")
            or drift.get("gomod_version")
            or drift.get("pyproject_version")
            or drift.get("makefile_version")
            or drift.get("cargo_version")
            or drift.get("gradle_version")
            or drift.get("maven_version")
            or drift.get("terraform_version")
            or drift.get("circleci_image")
            or drift.get("gitlab_image")
            or drift.get("k8s_image")
            or drift.get("helm_image")
            or drift.get("compose_image")
            or drift.get("dotnet_version")
            or drift.get("ruby_version")
            or drift.get("php_version")
            or drift.get("swift_version")
            or drift.get("deno_json_version")
            or drift.get("dart_version")
            or drift.get("mix_version")
            or drift.get("cmake_version")
            or drift.get("pipfile_version")
            or drift.get("catalog_version")
            or drift.get("taskfile_version")
            or drift.get("tool_versions_version")
            or drift.get("version_file")
            or ""
        )

    def _find_line(self, file_path: str, actual: str) -> int | None:
        """Find the line number containing the actual value."""
        if not file_path or not actual:
            return None
        full_path = self.root / file_path
        if not full_path.exists():
            return None
        try:
            content = full_path.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if actual in line:
                    return i
        except (OSError, UnicodeDecodeError):
            pass
        return None

    def _make_diff(self, actual: str, expected: str) -> str:
        """Generate a simple diff between actual and expected."""
        if actual == expected:
            return f"  {actual}"
        return f"- {actual}\n+ {expected}"

    def _suggest_fix(self, file_path: str, line: int | None, actual: str, expected: str) -> str:
        """Generate a human-readable fix suggestion."""
        if not file_path:
            return "No file associated with this drift."
        if not actual or not expected:
            return "Cannot determine fix — missing actual or expected value."
        location = f"{file_path}" + (f" line {line}" if line else "")
        return f"Update {location}: replace '{actual}' with '{expected}'"
