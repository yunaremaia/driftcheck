"""driftcheck CLI."""
from __future__ import annotations
import argparse, csv, json, io
import difflib
from pathlib import Path
from .detector import scan_repo, apply_fixes
from .sarif import to_sarif
from .config import DRIFT_KEYS
from .git_mode import (
    get_changed_and_untracked,
    get_staged_files,
    filter_detectors_by_files,
    DETECTOR_FILE_PATTERNS,
)

# Drift types that are informational (non-blocking) — reported but don't fail the check
INFORMATIONAL_DRIFTS = {"external_resource_drifts", "dependabot_drifts", "lockfile_drifts", "nvmrc_drifts", "typosquat_drifts"}

# Detector metadata: key -> (short_name, description)
DETECTOR_INFO = {
    "rust_drifts": ("rust-cargo", "Rust Cargo.toml rust-version vs README"),
    "node_drifts": ("node", "Node.js package.json engines vs README"),
    "bun_drifts": ("bun", "Bun package.json engines.bun vs README"),
    "package_version_drifts": ("package-version", "package.json version vs documentation"),
    "python_drifts": ("python", "Python pyproject.toml requires-python vs README"),
    "python_setup_drifts": ("python-setup", "Python setup.py/setup.cfg requirements vs docs"),
    "go_drifts": ("go", "Go go.mod directive vs README"),
    "docker_drifts": ("docker", "Dockerfile FROM tag vs README"),
    "docker_multistage_drifts": ("docker-multistage", "Multi-stage Dockerfile conflicting tags"),
    "docker_bases_drifts": ("docker-bases", "Floating/unpinned base images and sibling Dockerfile drift"),
    "java_drifts": ("gradle", "Gradle build.gradle sourceCompatibility vs README"),
    "maven_drifts": ("maven", "Maven pom.xml java.version vs README"),
    "terraform_drifts": ("terraform", "Terraform versions.tf provider vs README"),
    "circleci_drifts": ("circleci", "CircleCI config.yml image vs README"),
    "gitlab_drifts": ("gitlab", "GitLab CI image tag vs README"),
    "k8s_drifts": ("k8s", "Kubernetes manifest image vs README"),
    "helm_drifts": ("helm", "Helm Chart.yaml/values.yaml vs README"),
    "dc_drifts": ("compose", "Docker Compose image vs README"),
    "dotnet_drifts": ("dotnet", ".NET csproj TargetFramework vs README"),
    "ruby_drifts": ("ruby", "Gemfile ruby directive vs README"),
    "php_drifts": ("php", "composer.json require.php vs README"),
    "env_drifts": ("env", "Environment config drift (.env.example vs .env, compose overrides, Helm values)"),
    "env_example_drifts": ("env-example", ".env.example vs .env key drift"),
    "compose_override_drifts": ("compose-override", "Docker Compose override file image drift"),
    "helm_values_drifts": ("helm-values", "Helm values.yaml vs environment-specific values"),
    "actions_drifts": ("actions-node20", "GitHub Actions Node 20 deprecation"),
    "gh_actions_version_drifts": ("actions-outdated", "GitHub Actions outdated versions"),
    "ci_os_drifts": ("ci-os", "Deprecated CI runner (e.g., ubuntu-20.04)"),
    "lineending_drifts": ("lineending", "Missing .gitattributes line ending config"),
    "count_drifts": ("count", "Skills directory count vs README"),
    "external_resource_drifts": ("external", "External CDN resources in HTML (informational)"),
    "dependabot_drifts": ("dependabot", "Dependabot coverage gaps (informational)"),
    "lockfile_drifts": ("lockfile", "Lockfile missing/stale/orphaned (informational)"),
    "package_lock_drifts": ("package-lock", "package.json dependency ranges vs package-lock.json resolutions"),
    "tool_versions_drifts": ("tool-versions", ".tool-versions asdf/mise vs README"),
    "mise_drifts": ("mise", "mise.toml tool versions vs README"),
    "nvmrc_drifts": ("nvmrc", ".nvmrc vs package.json engines (informational)"),
    "swift_drifts": ("swift", "Swift Package.swift version pins vs README"),
    "deno_drifts": ("deno", "Deno deno.json version field vs README"),
    "dart_drifts": ("dart", "Dart pubspec.yaml SDK constraint vs README mentions"),
    "makefile_drifts": ("makefile", "Makefile tool version pins (CC, CMAKE, GO, etc.) vs README"),
    "elixir_drifts": ("elixir", "Elixir mix.exs version vs README"),
    "cmake_drifts": ("cmake", "CMakeLists.txt cmake_minimum_required version vs README"),
    "requirements_drifts": ("requirements", "requirements.txt package versions vs pyproject.toml/README"),
    "bazel_drifts": ("bazel", "Bazel pins vs README"),
    "nix_drifts": ("nix", "Nix flake.lock nixpkgs pins vs README"),
    "poetry_drifts": ("poetry", "Poetry pyproject.toml [tool.poetry] dependencies vs README"),
    "kotlin_drifts": ("kotlin", "Kotlin build.gradle.kts plugin version vs README"),
    "pipfile_drifts": ("pipfile", "Pipfile vs Pipfile.lock version mismatches"),
    "conda_drifts": ("conda", "Conda environment.yml pinned versions"),
    "gradle_catalog_drifts": ("gradle-catalog", "Gradle Version Catalog (libs.versions.toml)"),
    "kmp_drifts": ("kotlin-multiplatform", "Kotlin Multiplatform (KMP) version catalog drift"),
    "jenkins_drifts": ("jenkins", "Jenkinsfile tool versions (nodejs, python, docker) vs README"),
    "ruby_version_drifts": ("ruby-version", ".ruby-version vs README"),
    "python_version_drifts": ("python-version", ".python-version vs README"),
    "python_version_file_drifts": ("python-version-file", ".python-version vs requires-python floor"),
    "node_version_drifts": ("node-version", ".node-version vs README"),
    "java_version_drifts": ("java-version", ".java-version vs README"),
    "terraform_version_drifts": ("terraform-version", ".terraform-version vs README"),
    "taskfile_drifts": ("taskfile", "Taskfile.yml tool versions vs README"),
    "typosquat_drifts": ("typosquat", "Typosquat detection in dependencies (informational)"),
    "npmrc_drifts": ("npmrc", ".npmrc vs package.json settings (engine-strict, registry, tag-prefix)"),
    "yarnrc_drifts": ("yarnrc", ".yml Yarn version vs README"),
    "pnpm_workspace_drifts": ("pnpm", "pnpm-workspace.yaml vs package.json workspaces"),
    "package_manager_drifts": ("package-manager", "packageManager field vs lockfile"),
    "vscode_ext_drifts": ("vscode-ext", "VSCode extensions.json vs README recommendations"),
    "editorconfig_drifts": ("editorconfig", ".editorconfig vs README/IDE indent and style"),
    "git_tag_drifts": ("git-tag", "Latest git tag vs README version mentions"),
    "devcontainer_drifts": ("devcontainer", "Devcontainer.json features/base image vs README"),
    "pre_commit_drifts": ("pre-commit", "Pre-commit hook versions vs .pre-commit-config.yaml"),
}

# Mapping of project files to their relevant detectors for `driftcheck init`
FILE_DETECTOR_MAP = {
    "Cargo.toml": ["rust_drifts"],
    "package.json": ["node_drifts", "bun_drifts", "nvmrc_drifts", "package_lock_drifts", "package_version_drifts"],
    "go.mod": ["go_drifts"],
    "pyproject.toml": ["python_drifts"],
    "setup.py": ["python_setup_drifts"],
    "setup.cfg": ["python_setup_drifts"],
    "requirements.txt": ["requirements_drifts"],
    "Pipfile": ["pipfile_drifts"],
    "Dockerfile": ["docker_drifts", "docker_multistage_drifts", "docker_bases_drifts"],
    "docker-compose.yml": ["dc_drifts"],
    "docker-compose.yaml": ["dc_drifts"],
    "compose.yaml": ["dc_drifts"],
    "build.gradle": ["java_drifts"],
    "build.gradle.kts": ["kotlin_drifts"],
    "pom.xml": ["maven_drifts"],
    "versions.tf": ["terraform_drifts"],
    ".circleci/config.yml": ["circleci_drifts"],
    ".gitlab-ci.yml": ["gitlab_drifts"],
    "*.csproj": ["dotnet_drifts"],
    "Gemfile": ["ruby_drifts"],
    "composer.json": ["php_drifts"],
    ".tool-versions": ["tool_versions_drifts"],
    "mise.toml": ["mise_drifts"],
    "Package.swift": ["swift_drifts"],
    "deno.json": ["deno_drifts"],
    "deno.jsonc": ["deno_drifts"],
    "pubspec.yaml": ["dart_drifts"],
    "Makefile": ["makefile_drifts"],
    "GNUmakefile": ["makefile_drifts"],
    "mix.exs": ["elixir_drifts"],
    "CMakeLists.txt": ["cmake_drifts"],
    "Jenkinsfile": ["jenkins_drifts"],
    "libs.versions.toml": ["gradle_catalog_drifts"],
    ".pre-commit-config.yaml": ["pre_commit_drifts"],
    ".devcontainer/devcontainer.json": ["devcontainer_drifts"],
    "flake.nix": ["nix_drifts"],
    ".yarnrc.yml": ["yarnrc_drifts"],
    "pnpm-workspace.yaml": ["pnpm_workspace_drifts"],
    ".npmrc": ["npmrc_drifts"],
    ".editorconfig": ["editorconfig_drifts"],
    ".vscode/extensions.json": ["vscode_ext_drifts"],
    "Taskfile.yml": ["taskfile_drifts"],
    "environment.yml": ["conda_drifts"],
    "renovate.json": ["renovate_drifts"],
}


def _detect_detectors(root: Path) -> list[str]:
    """Auto-detect relevant detectors based on project files."""
    detected = set()
    
    # Map file patterns to detectors
    for pattern, detectors in FILE_DETECTOR_MAP.items():
        if pattern.startswith("*"):
            # Glob pattern
            matches = list(root.glob(pattern))
            if matches:
                detected.update(detectors)
        else:
            # Direct file check
            if (root / pattern).exists():
                detected.update(detectors)
    
    # Check for CI workflows
    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.exists():
        detected.add("actions_drifts")
        detected.add("gh_actions_version_drifts")
        detected.add("ci_os_drifts")
    
    # Check for kubernetes manifests
    if list(root.rglob("*.yaml")) or list(root.rglob("*.yml")):
        # Check for k8s files (Deployment, Service, etc.)
        for f in root.rglob("*.yaml"):
            try:
                content = f.read_text()[:2000]
                if "apiVersion:" in content and "kind:" in content:
                    detected.add("k8s_drifts")
                    break
            except:
                pass
    
    # Check for helm charts
    if (root / "Chart.yaml").exists() or list(root.rglob("Chart.yaml")):
        detected.add("helm_drifts")
    
    # Check for version manager files
    for vfile in [".ruby-version", ".python-version", ".node-version", ".java-version", ".terraform-version"]:
        if (root / vfile).exists():
            key = vfile.lstrip(".").replace("-", "_") + "_drifts"
            if key in DETECTOR_INFO:
                detected.add(key)
    
    return sorted(detected)


def _generate_init_config(root: Path) -> str:
    """Generate a .driftcheck.toml config based on detected project type."""
    detected = _detect_detectors(root)
    
    if not detected:
        return (
            "[driftcheck]\n"
            "# No project-specific files detected.\n"
            "# Uncomment detectors below based on your project type.\n"
            "# exclude_detectors = []\n"
            "# doc_paths = [\"README.md\", \"docs/\"]\n"
            "# fail_on_informational = false\n"
        )
    
    # Build exclude list: exclude detectors NOT detected (to reduce noise)
    all_detectors = set(DETECTOR_INFO.keys())
    # Keep only blocking detectors that were detected
    detected_blocking = [d for d in detected if d not in INFORMATIONAL_DRIFTS]
    
    exclude = sorted(all_detectors - set(detected))
    # Don't exclude informational ones by default — they're non-blocking
    
    lines = [
        "[driftcheck]",
        f"# Auto-generated by driftcheck init ({len(detected_blocking)} detectors enabled)",
        f"# Detected project files: {', '.join(_detect_project_files(root))}",
        "",
        "# Detectors enabled (auto-detected):",
    ]
    for d in detected_blocking:
        meta = DETECTOR_INFO.get(d)
        if meta:
            lines.append(f"#   - {meta[0]}: {meta[1]}")
    
    lines.extend([
        "",
        "# Uncomment to exclude detectors not relevant to your project:",
        f"# exclude_detectors = [{', '.join(repr(e) for e in exclude[:10])}{', ...' if len(exclude) > 10 else ''}]",
        "",
        "# Additional options:",
        "# doc_paths = [\"docs/setup.md\"]  # scan extra docs",
        "# fail_on_informational = false",
        "# follow_symlinks = true",
    ])
    
    return "\n".join(lines) + "\n"


def _detect_project_files(root: Path) -> list[str]:
    """Return list of detected project files for display."""
    found = []
    check_files = [
        "Cargo.toml", "package.json", "go.mod", "pyproject.toml", "requirements.txt",
        "Dockerfile", "docker-compose.yml", "build.gradle", "build.gradle.kts", "pom.xml",
        "*.csproj", "Gemfile", "composer.json", "Makefile", "CMakeLists.txt",
        "Jenkinsfile", ".pre-commit-config.yaml", "Package.swift", "pubspec.yaml",
    ]
    for f in check_files:
        if f.startswith("*"):
            if list(root.glob(f)):
                found.append(f)
        elif (root / f).exists():
            found.append(f)
    return found[:8]  # limit display


def _validate_detector_names(names: set[str], source: str) -> list[str]:
    """Validate detector names against known detector keys."""
    known = set(DETECTOR_INFO.keys())
    unknown = []
    for name in names:
        if name not in known:
            unknown.append(name)
            suggestions = difflib.get_close_matches(name, known, n=3, cutoff=0.6)
            if suggestions:
                print(f"driftcheck: unknown detector '{name}' (from {source}) — did you mean: {', '.join(suggestions)}?", file=__import__('sys').stderr)
            else:
                print(f"driftcheck: unknown detector '{name}' (from {source}) — run --list-detectors for valid names", file=__import__('sys').stderr)
    return unknown


def _pre_commit_hook_entry() -> str:
    return """- id: driftcheck
  name: driftcheck
  description: Detect version drift in staged repository changes
  entry: driftcheck --changed-only
  language: python
  pass_filenames: false
  always_run: true"""


def main(argv=None) -> int:
    raw_argv = list(argv) if argv is not None else __import__("sys").argv[1:]
    if raw_argv and raw_argv[0] == "pre-commit":
        print(_pre_commit_hook_entry())
        return 0

    ap = argparse.ArgumentParser(
        prog="driftcheck",
        description="Detect version drift between docs and toolchain files.",
    )
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    ap.add_argument("--csv", action="store_true", dest="as_csv", help="CSV output (for spreadsheets/data pipelines)")
    ap.add_argument("--sarif", action="store_true", dest="as_sarif", help="SARIF 2.1.0 output (for GitHub Code Scanning)")
    ap.add_argument("--absolute-paths", action="store_true", default=False, help="use absolute paths in SARIF output (default: relative for CI privacy)")
    ap.add_argument("--fix", action="store_true", help="auto-fix detected drifts in documentation files")
    ap.add_argument("--version", action="version", version=_version())
    ap.add_argument("--quiet", "-q", action="store_true", help="only output drifts, suppress OK messages")
    ap.add_argument("--no-informational", action="store_true", help="skip informational drifts in output")
    ap.add_argument("--list-detectors", action="store_true", help="list available detectors and exit")
    ap.add_argument("--only", metavar="DETECTOR", help="run only specified detectors (comma-separated)")
    ap.add_argument("--exclude", metavar="DETECTOR", help="exclude specified detectors (comma-separated)")
    ap.add_argument("--report", action="store_true", help="output a markdown report (for CI job summaries / PR comments)")
    ap.add_argument("--init", action="store_true", help="generate a .driftcheck.toml config file and exit")
    ap.add_argument("--force", action="store_true", help="overwrite existing config (with --init)")
    ap.add_argument("--dry-run", action="store_true", help="print config to stdout without writing (with --init)")
    ap.add_argument("--git-mode", action="store_true", help="only scan files changed since --git-base (default: HEAD~1)")
    ap.add_argument("--changed-only", action="store_true", help="only run detectors relevant to files staged for commit")
    ap.add_argument("--git-base", metavar="COMMIT", default="HEAD~1", help="base commit for --git-mode (default: HEAD~1); validated against strict ref format")
    ap.add_argument("--max-file-size", type=int, default=None, metavar="BYTES", help="max file size in bytes (default: 1MB from config); larger files are skipped")
    ap.add_argument("--explain", metavar="DRIFT_ID", help="explain a specific drift (format: detector:file)")
    ap.add_argument("--explain-all", action="store_true", help="explain all detected drifts")
    ap.add_argument("--explain-format", choices=["text", "json"], default="text", help="output format for --explain (default: text)")
    ap.add_argument("--explain-fix", action="store_true", help="apply suggested fixes with --explain or --explain-all")
    ap.add_argument("--doctor", action="store_true", help="run repository diagnostics (pre-scan checks)")
    ap.add_argument("--doctor-json", action="store_true", help="output doctor results as JSON")
    ap.add_argument("--doctor-fix", action="store_true", help="auto-fix doctor-detected issues")
    ap.add_argument("--baseline", action="store_true", help="create baseline from current state (accept all current drifts as known good)")
    ap.add_argument("--baseline-update", action="store_true", help="update baseline to current state (preserves first_seen for existing drifts)")
    ap.add_argument("--baseline-reset", action="store_true", help="remove baseline file")
    ap.add_argument("--baseline-show", action="store_true", help="display baseline contents")
    args = ap.parse_args(raw_argv)

    if args.list_detectors:
        _list_detectors()
        return 0

    if getattr(args, "doctor", False):
        from .doctor import run_doctor, print_doctor_report, doctor_exit_code, doctor_fix
        root = Path(args.path)
        report = run_doctor(root)
        if args.doctor_json:
            print_doctor_report(report, json_mode=True)
        else:
            print_doctor_report(report)
        if getattr(args, "doctor_fix", False):
            fixes = doctor_fix(root, report)
            if fixes:
                print()
                print("Auto-fixed:")
                for f in fixes:
                    print(f"  ✓ {f}")
        return doctor_exit_code(report)

    if args.init:
        return _init_config(Path(args.path), force=args.force, dry_run=args.dry_run)

    # Baseline mode: create/update/reset/show baseline
    if args.baseline or args.baseline_update or args.baseline_reset or args.baseline_show:
        from .baseline import create_baseline, update_baseline, reset_baseline, show_baseline, load_baseline, compare_against_baseline
        root = Path(args.path)
        if args.baseline:
            result = scan_repo(root)
            baseline = create_baseline(root, result)
            print(f"driftcheck: baseline created — {baseline['total_entries']} drift(s) recorded")
            print(f"driftcheck: baseline file: {root / '.driftcheck-baseline.json'}")
            return 0
        if args.baseline_update:
            result = scan_repo(root)
            baseline = update_baseline(root, result)
            print(f"driftcheck: baseline updated — {baseline['total_entries']} drift(s) recorded")
            return 0
        if args.baseline_reset:
            removed = reset_baseline(root)
            if removed:
                print("driftcheck: baseline removed")
            else:
                print("driftcheck: no baseline to remove")
            return 0
        if args.baseline_show:
            print(show_baseline(root))
            return 0

    # Explain mode: explain drifts without re-scanning
    if args.explain or args.explain_all:
        from .explain import Explainer
        root = Path(args.path)
        result = scan_repo(root, enabled_detectors=None, max_file_size=args.max_file_size)
        explainer = Explainer(root)

        if args.explain_all:
            explanations = explainer.explain_all(result)
            if args.explain_format == "json":
                print(json.dumps(explanations, indent=2))
            else:
                for exp in explanations:
                    print(f"Drift: {exp['drift']}")
                    print(f"  File: {exp['file']}" + (f" (line {exp['line']})" if exp['line'] else ""))
                    print(f"  Actual: {exp['actual']}")
                    print(f"  Expected: {exp['expected']}")
                    print(f"  Diff: {exp['diff']}")
                    print(f"  Impact: {exp['impact']}")
                    print(f"  Fix: {exp['fix']}")
                    print()
            if args.explain_fix:
                fixed = []
                for drift_type, drifts in result.items():
                    if not isinstance(drifts, list):
                        continue
                    for drift in drifts:
                        if isinstance(drift, dict):
                            result_fix = explainer.explain_fix(drift, drift_type)
                            if result_fix:
                                fixed.append(result_fix)
                if fixed:
                    print(f"driftcheck: fixed {len(fixed)} file(s): {', '.join(fixed)}")
            return 0

        # Single drift explain
        drift_id = args.explain
        # Parse drift_id as "detector:file" or just "detector"
        parts = drift_id.split(":", 1)
        detector = parts[0]
        file_filter = parts[1] if len(parts) > 1 else None

        found = False
        for drift_type, drifts in result.items():
            if not isinstance(drifts, list):
                continue
            if drift_type != detector:
                continue
            for drift in drifts:
                if not isinstance(drift, dict):
                    continue
                if file_filter and drift.get("file") != file_filter:
                    continue
                if args.explain_format == "json":
                    print(json.dumps(explainer.explain_json(drift, drift_type), indent=2))
                else:
                    print(explainer.explain_text(drift, drift_type))
                found = True
                if args.explain_fix:
                    fixed = explainer.explain_fix(drift, drift_type)
                    if fixed:
                        print(f"driftcheck: fixed {fixed}")
                break
            if found:
                break
        if not found:
            print(f"driftcheck: drift '{drift_id}' not found", file=__import__('sys').stderr)
            return 1
        return 0

    # Git/pre-commit modes: determine which detectors to run based on changed files
    enabled_detectors = None
    if args.changed_only:
        changed = get_staged_files(Path(args.path))
        if not changed:
            if not args.quiet:
                print("driftcheck: no staged files")
            return 0
        enabled_detectors = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        if not args.quiet:
            print(f"driftcheck: changed-only — {len(changed)} staged file(s), {len(enabled_detectors)} detector(s) relevant")
    elif args.git_mode:
        changed = get_changed_and_untracked(Path(args.path), args.git_base)
        if not changed:
            if not args.quiet:
                print(f"driftcheck: no files changed since {args.git_base}")
            return 0
        enabled_detectors = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        if not args.quiet:
            print(f"driftcheck: git-mode — {len(changed)} file(s) changed, {len(enabled_detectors)} detector(s) relevant")

    result = scan_repo(Path(args.path), enabled_detectors=enabled_detectors, max_file_size=args.max_file_size)

    # Baseline integration: compare against baseline if one exists
    from .baseline import load_baseline, compare_against_baseline
    root = Path(args.path)
    baseline = load_baseline(root)
    if baseline:
        comparison = compare_against_baseline(root, result, baseline)
        # Add baseline info to result for JSON/SARIF output
        result["_baseline"] = {
            "info": comparison["baseline_info"],
            "new_drift_count": sum(len(v) for v in comparison["new_drifts"].values()),
            "pre_existing_drift_count": sum(len(v) for v in comparison["pre_existing_drifts"].values()),
        }
        # For text output, show pre-existing drifts as informational
        if not args.quiet and comparison["pre_existing_drifts"] and not args.as_json:
            total_pre = sum(len(v) for v in comparison["pre_existing_drifts"].values())
            print(f"driftcheck: {total_pre} pre-existing drift(s) in baseline (not failing)")
    else:
        comparison = None

    if args.report:
        _print_report(result)
        blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}
        return 1 if any(blocking.values()) else 0

    # Filter detectors if requested (with validation)
    if args.only:
        wanted = {d.strip() for d in args.only.split(",")}
        unknown = _validate_detector_names(wanted, "--only")
        if unknown:
            unknown_set = set(unknown)
            valid_wanted = wanted - unknown_set
            if not valid_wanted:
                print(f"driftcheck: error: no valid detector names in --only, aborting", file=__import__('sys').stderr)
                return 2
        result = {k: v for k, v in result.items() if k in wanted or not k.endswith("_drifts")}
    if args.exclude:
        excluded = {d.strip() for d in args.exclude.split(",")}
        unknown = _validate_detector_names(excluded, "--exclude")
        if unknown:
            unknown_set = set(unknown)
            excluded = excluded - unknown_set
        result = {k: v for k, v in result.items() if k not in excluded}

    if args.as_sarif:
        from . import __version__
        root = Path(args.path) if not args.absolute_paths else None
        sarif_doc = to_sarif(result, version=__version__, root=root)
        # Add baseline info to SARIF if present
        if baseline and comparison:
            sarif_doc["runs"][0]["properties"] = sarif_doc["runs"][0].get("properties", {})
            sarif_doc["runs"][0]["properties"]["baseline"] = result.get("_baseline", {})
        print(json.dumps(sarif_doc, indent=2))
        blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}
        return 1 if any(blocking.values()) else 0

    if args.no_informational:
        result = {k: v for k, v in result.items() if k not in INFORMATIONAL_DRIFTS}

    if args.as_csv:
        _print_csv(result)
        blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}
        return 1 if any(blocking.values()) else 0

    if args.fix:
        fixed = apply_fixes(Path(args.path), result)
        if fixed:
            print(f"driftcheck: fixed {len(fixed)} file(s): {', '.join(fixed)}")
            return 0
        else:
            print("driftcheck: no drifts to fix")
            return 0

    all_drifts = {k: result.get(k, []) for k in DRIFT_KEYS}
    blocking_drifts = {k: v for k, v in all_drifts.items() if k not in INFORMATIONAL_DRIFTS}

    # When baseline exists, only NEW drifts are blocking (pre-existing are warnings)
    if baseline and comparison:
        new_blocking = {k: v for k, v in comparison["new_drifts"].items() if k not in INFORMATIONAL_DRIFTS}
        has_blocking = any(new_blocking.values())
    else:
        has_blocking = any(blocking_drifts.values())

    has_any_drift = any(all_drifts.values())

    if args.as_json:
        print(json.dumps(result, indent=2))
        if baseline and comparison:
            # When baseline exists, only NEW drifts make it fail
            new_blocking = {k: v for k, v in comparison["new_drifts"].items() if k not in INFORMATIONAL_DRIFTS}
            return 1 if any(new_blocking.values()) else 0
        return 1 if has_blocking else 0

    tv = result.get("toolchain_version")
    cv = result.get("cargo_rust_version")
    nv = result.get("package_node")
    pv = result.get("pyproject_python")
    gv = result.get("gomod_version")

    has_toolchain = tv or cv or nv or pv or gv

    # Also check for other project types (Ruby, .NET, Docker, PHP, etc.)
    if not has_toolchain:
        path = Path(args.path)
        other_indicators = [
            "Gemfile", "Dockerfile", "docker-compose.yml", "compose.yaml",
            "Dockerfile.*", "docker/Dockerfile", "*.csproj", "*.sln", "composer.json",
            "pubspec.yaml", "Package.swift", "deno.json", "deno.jsonc", ".tool-versions", ".nvmrc",
            "Makefile", "makefile", "GNUmakefile", "Makefile.*", "make/*.mk",
            "mix.exs", "CMakeLists.txt", "Jenkinsfile", "jenkinsfile",
        ]
        for pattern in other_indicators:
            if list(path.glob(pattern)):
                has_toolchain = True
                break
        # Check subdirectories for project files
        if not has_toolchain:
            for subdir in ["src", "lib", "app", "test", "tests", "scripts", "bin", "pkg", "cmd"]:
                subpath = path / subdir
                if subpath.exists():
                    for pattern in other_indicators:
                        if list(subpath.glob(pattern)):
                            has_toolchain = True
                            break
                if has_toolchain:
                    break

    # No toolchain and no drifts at all — truly empty repo
    if not has_toolchain and not has_any_drift:
        if not args.quiet:
            print("driftcheck: no toolchain version found")
        return 0

    # No blocking drifts — print OK, then informational drifts
    if not has_blocking:
        if not args.quiet:
            parts = []
            if tv: parts.append(f"Rust {tv}")
            if cv: parts.append(f"Rust(Cargo) {cv}")
            if nv: parts.append(f"Node {nv}")
            if pv: parts.append(f"Python {pv}")
            if gv: parts.append(f"Go {gv}")
            base = f"driftcheck: OK — all docs match {' + '.join(parts)}" if parts else "driftcheck: OK"
            print(base)
        if not args.no_informational:
            _print_informational(all_drifts)
        return 0

    # Print blocking drifts
    if baseline and comparison:
        # When baseline exists, show new drifts as blocking, pre-existing as informational
        _print_blocking_drifts(comparison["new_drifts"], result)
        if not args.no_informational:
            _print_informational(all_drifts)
            # Also show pre-existing drifts
            if comparison["pre_existing_drifts"]:
                print()
                print("Pre-existing drifts (in baseline):")
                _print_blocking_drifts(comparison["pre_existing_drifts"], result)
    else:
        _print_blocking_drifts(all_drifts, result)
        if not args.no_informational:
            _print_informational(all_drifts)
    return 1


def _version() -> str:
    from . import __version__
    return f"%(prog)s {__version__}"


def _init_config(root: Path, force: bool = False, dry_run: bool = False) -> int:
    """Generate a .driftcheck.toml config file with auto-detected project type."""
    config_text = _generate_init_config(root)
    config_path = root / ".driftcheck.toml"

    if dry_run:
        print(config_text, end="")
        return 0

    if config_path.exists() and not force:
        print(f"driftcheck: {config_path} already exists — use --force to overwrite")
        return 1

    config_path.write_text(config_text, encoding="utf-8")
    print(f"driftcheck: created {config_path} (auto-detected project type)")
    return 0


def _print_report(result: dict) -> None:
    """Output a markdown report of all drifts with statistical summary."""
    blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}
    informational = {k: result.get(k, []) for k in DRIFT_KEYS if k in INFORMATIONAL_DRIFTS}
    has_blocking = any(blocking.values())
    has_informational = any(informational.values())

    print("## driftcheck report\n")

    # Statistical summary
    total_blocking = sum(len(v) for v in blocking.values())
    total_informational = sum(len(v) for v in informational.values())
    total_drifts = total_blocking + total_informational

    if total_drifts > 0:
        print("### 📊 Summary\n")
        print(f"- **Total drifts:** {total_drifts}")
        print(f"  - ❌ Blocking: {total_blocking}")
        print(f"  - ℹ️  Informational: {total_informational}")

        # Detector breakdown
        detectors_fired = []
        for key, drifts in {**blocking, **informational}.items():
            if drifts:
                meta = DETECTOR_INFO.get(key)
                name = meta[0] if meta else key
                detectors_fired.append((name, len(drifts)))
        if detectors_fired:
            detectors_fired.sort(key=lambda x: -x[1])
            print(f"- **Detectors fired:** {len(detectors_fired)}")
            for name, count in detectors_fired:
                print(f"  - `{name}`: {count}")

        # Top files with most drifts
        file_counts: dict[str, int] = {}
        for key, drifts in {**blocking, **informational}.items():
            for d in drifts:
                if isinstance(d, dict):
                    fname = d.get("file", "?")
                    file_counts[fname] = file_counts.get(fname, 0) + 1
        if file_counts:
            top_files = sorted(file_counts.items(), key=lambda x: -x[1])[:5]
            print(f"- **Top files:**")
            for fname, count in top_files:
                print(f"  - `{fname}`: {count} drift(s)")

        print()

    if not has_blocking and not has_informational:
        print("✅ No drift detected — docs match toolchain.")
        return

    if has_blocking:
        print("### ❌ Blocking drifts\n")
        for key, drifts in blocking.items():
            if not drifts:
                continue
            meta = DETECTOR_INFO.get(key)
            if meta:
                print(f"**{meta[1]}** ({key}):")
            for d in drifts:
                file = d.get("file", "?")
                detail = d.get("detail", "")
                if detail:
                    print(f"- `{file}`: {detail}")
                else:
                    tool = d.get("tool", "")
                    doc_v = d.get("doc_version", "")
                    actual_v = d.get("makefile_version", d.get("package_version", d.get("gomod_version", d.get("pyproject_version", d.get("requirements_version", d.get("gradle_version", ""))))))
                    if tool:
                        print(f"- `{file}`: {tool} {doc_v} → should be {actual_v}")
                    else:
                        print(f"- `{file}`: {d}")
            print()

    if has_informational:
        print("### ℹ️  Informational\n")
        for key, drifts in informational.items():
            if not drifts:
                continue
            meta = DETECTOR_INFO.get(key)
            if meta:
                print(f"**{meta[1]}** ({key}):")
            for d in drifts:
                file = d.get("file", "?")
                detail = d.get("detail", str(d))
                print(f"- `{file}`: {detail}")
            print()


def _print_csv(result: dict) -> None:
    """Output drifts as CSV (columns: file,detector,doc_version,actual_version,severity,message)."""
    rows = []
    for key, drifts in result.items():
        if not isinstance(drifts, list) or not drifts:
            continue
        severity = "informational" if key in INFORMATIONAL_DRIFTS else "blocking"
        short_name = DETECTOR_INFO.get(key, (key,))[0]
        for d in drifts:
            if not isinstance(d, dict):
                continue
            actual_v = (
                d.get("suggested")
                or d.get("toolchain_version")
                or d.get("package_version")
                or d.get("gomod_version")
                or d.get("pyproject_version")
                or d.get("makefile_version")
                or d.get("cargo_version")
                or d.get("gradle_version")
                or d.get("maven_version")
                or d.get("terraform_version")
                or d.get("circleci_image")
                or d.get("gitlab_image")
                or d.get("k8s_image")
                or d.get("helm_image")
                or d.get("compose_image")
                or d.get("dotnet_version")
                or d.get("ruby_version")
                or d.get("php_version")
                or d.get("swift_version")
                or d.get("deno_json_version")
                or d.get("dart_version")
                or d.get("mix_version")
                or d.get("cmake_version")
                or d.get("pipfile_version")
                or d.get("catalog_version")
                or d.get("taskfile_version")
                or d.get("tool_versions_version")
                or d.get("version_file")
                or ""
            )
            rows.append({
                "file": d.get("file", ""),
                "detector": short_name,
                "doc_version": d.get("doc_version", d.get("doc_image", d.get("tool", ""))),
                "actual_version": actual_v,
                "severity": severity,
                "message": d.get("detail", ""),
            })

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["file", "detector", "doc_version", "actual_version", "severity", "message"],
    )
    writer.writeheader()
    writer.writerows(rows)
    print(output.getvalue(), end="")


def _list_detectors() -> None:
    """Print available detectors."""
    print("driftcheck detectors:")
    for key, (short, desc) in DETECTOR_INFO.items():
        blocking = "blocking" if key not in INFORMATIONAL_DRIFTS else "informational"
        print(f"  {short:20s} [{blocking:14s}] {desc}")


def _print_blocking_drifts(all_drifts: dict, result: dict) -> None:
    """Print all blocking drift types."""
    for d in all_drifts.get("rust_drifts", []):
        target = d.get("toolchain_version") or d.get("cargo_version")
        print(f"driftcheck: {d['file']}: Rust {d['doc_version']} → should be {target}")
    for d in all_drifts.get("node_drifts", []):
        print(f"driftcheck: {d['file']}: Node {d['doc_version']} → should be {d['package_version']}")
    for d in all_drifts.get("bun_drifts", []):
        print(f"driftcheck: {d['file']}: Bun {d['doc_version']} → should be {d['package_version']} (package.json)")
    for d in all_drifts.get("package_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['package']} {d['doc_version']} → should be {d['package_version']} (package.json)")
    for d in all_drifts.get("python_drifts", []):
        print(f"driftcheck: {d['file']}: Python {d['doc_version']} → should be {d['pyproject_version']}")
    for d in all_drifts.get("python_setup_drifts", []):
        if d.get("type") == "python_requires":
            print(f"driftcheck: {d['file']}: Python {d['doc_version']} → should be {d['setup_version']} ({d['source']})")
        else:
            print(f"driftcheck: {d['file']}: {d['package']} {d['doc_version']} → should be {d['setup_version']} ({d['source']})")
    for d in all_drifts.get("go_drifts", []):
        print(f"driftcheck: {d['file']}: Go {d['doc_version']} → should be {d['gomod_version']}")
    for d in all_drifts.get("count_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_count']} skills → should be {d['actual_count']} (skills/ count)")
    for d in all_drifts.get("actions_drifts", []):
        print(f"driftcheck: {d['file']}: {d['action']}@{d['current']} → should be {d['suggested']} (node20→node24)")
    for d in all_drifts.get("lineending_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")
    for d in all_drifts.get("docker_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['dockerfile_image']} (Dockerfile)")
    for d in all_drifts.get("docker_multistage_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")
    for d in all_drifts.get("docker_bases_drifts", []):
        if 'tags' in d:
            print(f"driftcheck: {d['image']} pinned differently across {', '.join(d['tags'])}")
        else:
            print(f"driftcheck: {d['file']}:{d['line']}: {d['image']}:{d.get('tag', '(none)')} uses floating tag")
    for d in all_drifts.get("java_drifts", []):
        print(f"driftcheck: {d['file']}: Java {d['doc_version']} → should be {d['gradle_version']} (build.gradle)")
    for d in all_drifts.get("maven_drifts", []):
        print(f"driftcheck: {d['file']}: Java {d['doc_version']} → should be {d['maven_version']} (pom.xml)")
    for d in all_drifts.get("terraform_drifts", []):
        print(f"driftcheck: {d['file']}: Terraform {d['provider']} {d['doc_version']} → should be {d['terraform_version']}")
    for d in all_drifts.get("circleci_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['circleci_image']} (CircleCI)")
    for d in all_drifts.get("gitlab_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['gitlab_image']} (GitLab CI)")
    for d in all_drifts.get("k8s_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['k8s_image']} (Kubernetes)")
    for d in all_drifts.get("gh_actions_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['action']}@{d['current']} → should be {d['suggested']}")
    for d in all_drifts.get("helm_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_version']} → should be {d['helm_image']} (Helm chart)")
    for d in all_drifts.get("dc_drifts", []):
        print(f"driftcheck: {d['file']}: {d['doc_version']} → should be {d['compose_image']} (Docker Compose)")
    for d in all_drifts.get("ci_os_drifts", []):
        print(f"driftcheck: {d['file']}: {d['runner']} → should be {d['suggested']} (deprecated CI runner)")
    for d in all_drifts.get("dotnet_drifts", []):
        print(f"driftcheck: {d['file']}: .NET {d['doc_version']} → should be {d['csproj_version']} (.csproj)")
    for d in all_drifts.get("ruby_drifts", []):
        print(f"driftcheck: {d['file']}: Ruby {d['doc_version']} → should be {d['gemfile_version']} (Gemfile)")
    for d in all_drifts.get("php_drifts", []):
        print(f"driftcheck: {d['file']}: PHP {d['doc_version']} → should be {d['composer_version']} (composer.json)")
    for d in all_drifts.get("tool_versions_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['tool_versions_version']} (.tool-versions)")
    for d in all_drifts.get("taskfile_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['taskfile_version']} (Taskfile.yml)")
    for d in all_drifts.get("swift_drifts", []):
        print(f"driftcheck: {d['file']}: Swift {d['doc_version']} → should be {d['package_version']} (Package.swift)")
    for d in all_drifts.get("deno_drifts", []):
        print(f"driftcheck: {d['file']}: Deno {d['doc_version']} → should be {d['deno_json_version']} (deno.json)")
    for d in all_drifts.get("dart_drifts", []):
        print(f"driftcheck: {d['file']}: Dart {d['doc_version']} → should be {d['pubspec_version']} (pubspec.yaml)")

    # Makefile drifts
    for d in all_drifts.get("makefile_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['makefile_version']} (Makefile)")

    # Elixir drifts
    for d in all_drifts.get("elixir_drifts", []):
        print(f"driftcheck: {d['file']}: Elixir {d['doc_version']} → should be {d['mix_version']} (mix.exs)")

    # CMake drifts
    for d in all_drifts.get("cmake_drifts", []):
        print(f"driftcheck: {d['file']}: CMake {d['doc_version']} → should be {d['cmake_version']} (CMakeLists.txt)")

    # Requirements drifts
    for d in all_drifts.get("requirements_drifts", []):
        print(f"driftcheck: {d['file']}: {d['package']} {d['doc_version']} → should be {d['requirements_version']} (requirements.txt)")

    # Kotlin drifts
    for d in all_drifts.get("kotlin_drifts", []):
        print(f"driftcheck: {d['file']}: Kotlin {d['doc_version']} → should be {d['gradle_version']} (build.gradle.kts)")

    # Pipfile drift
    for d in all_drifts.get("pipfile_drifts", []):
        print(f"driftcheck: {d['file']}: {d['package']}: Pipfile={d['pipfile_version']} vs Pipfile.lock={d['lock_version']}")

    # Conda drift
    for d in all_drifts.get("conda_drifts", []):
        print(f"driftcheck: {d['file']}: {d['package']}: {d.get('environment_version', 'unpinned')} version pin")

    # Poetry drift
    for d in all_drifts.get("poetry_drifts", []):
        print(f"driftcheck: {d['file']}: {d['package']} {d['doc_version']} → should be {d['pyproject_version']} (pyproject.toml)")

    # Gradle Version Catalog drift
    for d in all_drifts.get("gradle_catalog_drifts", []):
        print(f"driftcheck: {d['file']}: {d['library']}: catalog={d['catalog_version']} vs README={d['readme_version']}")

    # NPMRC drifts
    for d in all_drifts.get("npmrc_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # Jenkins drifts
    for d in all_drifts.get("jenkins_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['jenkins_version']} (Jenkinsfile)")

    # Version file drifts
    for d in all_drifts.get("ruby_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['version_file']} (.ruby-version)")
    for d in all_drifts.get("python_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['version_file']} (.python-version)")
    for d in all_drifts.get("python_version_file_drifts", []):
        print(f"driftcheck: .python-version {d['pin_version']} is below {d['floor_source']} requires-python floor {d['floor_version']}")
    for d in all_drifts.get("node_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['version_file']} (.node-version)")
    for d in all_drifts.get("java_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['version_file']} (.java-version)")
    for d in all_drifts.get("terraform_version_drifts", []):
        print(f"driftcheck: {d['file']}: {d['tool']} {d['doc_version']} → should be {d['version_file']} (.terraform-version)")

    # NPMRC drifts
    for d in all_drifts.get("npmrc_drifts", []):
        print(f"driftcheck: {d['file']}: npm registry {d['doc_registry']} → should be {d['npmrc_registry']} (.npmrc)")

    # Yarn RC drifts
    for d in all_drifts.get("yarnrc_drifts", []):
        print(f"driftcheck: {d['file']}: Yarn {d['doc_version']} → should be {d['yarnrc_version']} (.yml)")

    # PNPM workspace drifts
    for d in all_drifts.get("pnpm_workspace_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # Package manager drifts
    for d in all_drifts.get("package_manager_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # package-lock integrity drifts are blocking supply-chain findings
    for d in all_drifts.get("package_lock_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # VSCode extensions drifts
    for d in all_drifts.get("vscode_ext_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # EditorConfig drifts
    for d in all_drifts.get("editorconfig_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # Git tag drifts
    for d in all_drifts.get("git_tag_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # Environment drifts
    for d in all_drifts.get("env_drifts", []):
        print(f"driftcheck: {d['file']}: {d['detail']}")

    # Plugin drifts (generic handler)
    for key, drifts in all_drifts.items():
        if key.startswith("plugin_") and key.endswith("_drifts"):
            for d in drifts:
                detail = d.get("detail", d.get("doc_version", str(d)))
                fname = d.get("file", "unknown")
                print(f"driftcheck: {fname}: {detail}")


def _print_informational(all_drifts: dict) -> None:
    """Print informational (non-blocking) drift types."""
    for d in all_drifts.get("external_resource_drifts", []):
        print(f"driftcheck: info: {d['file']}: {d['detail']} ({d['url']})")
    for d in all_drifts.get("dependabot_drifts", []):
        if d.get("kind") == "dependabot_missing":
            print(f"driftcheck: info: {d['file']}: missing — {d['detail']}")
        else:
            print(f"driftcheck: info: {d['file']}: incomplete — {d['detail']}")
    for d in all_drifts.get("lockfile_drifts", []):
        if d.get("kind") == "lockfile_missing":
            print(f"driftcheck: info: {d['file']}: missing — {d['detail']}")
        elif d.get("kind") == "lockfile_stale":
            print(f"driftcheck: info: {d['file']}: stale — {d['detail']}")
        elif d.get("kind") == "lockfile_orphaned":
            print(f"driftcheck: info: {d['file']}: orphaned — {d['detail']}")
    for d in all_drifts.get("nvmrc_drifts", []):
        print(f"driftcheck: info: {d['file']}: Node {d.get('doc_version')} → should be {d.get('nvmrc_version')} (.nvmrc)")


if __name__ == "__main__":
    raise SystemExit(main())
