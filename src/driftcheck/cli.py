"""driftcheck CLI."""
from __future__ import annotations
import argparse, csv, json, io
from pathlib import Path
from .detector import scan_repo, apply_fixes
from .sarif import to_sarif
from .config import DRIFT_KEYS
from .git_mode import get_changed_and_untracked, filter_detectors_by_files, DETECTOR_FILE_PATTERNS

# Drift types that are informational (non-blocking) — reported but don't fail the check
INFORMATIONAL_DRIFTS = {"external_resource_drifts", "dependabot_drifts", "lockfile_drifts", "nvmrc_drifts", "typosquat_drifts"}

# Detector metadata: key -> (short_name, description)
DETECTOR_INFO = {
    "rust_drifts": ("rust-cargo", "Rust Cargo.toml rust-version vs README"),
    "node_drifts": ("node", "Node.js package.json engines vs README"),
    "bun_drifts": ("bun", "Bun package.json engines.bun vs README"),
    "python_drifts": ("python", "Python pyproject.toml requires-python vs README"),
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="driftcheck",
        description="Detect version drift between docs and toolchain files.",
    )
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    ap.add_argument("--csv", action="store_true", dest="as_csv", help="CSV output (for spreadsheets/data pipelines)")
    ap.add_argument("--sarif", action="store_true", dest="as_sarif", help="SARIF 2.1.0 output (for GitHub Code Scanning)")
    ap.add_argument("--fix", action="store_true", help="auto-fix detected drifts in documentation files")
    ap.add_argument("--version", action="version", version=_version())
    ap.add_argument("--quiet", "-q", action="store_true", help="only output drifts, suppress OK messages")
    ap.add_argument("--no-informational", action="store_true", help="skip informational drifts in output")
    ap.add_argument("--list-detectors", action="store_true", help="list available detectors and exit")
    ap.add_argument("--only", metavar="DETECTOR", help="run only specified detectors (comma-separated)")
    ap.add_argument("--exclude", metavar="DETECTOR", help="exclude specified detectors (comma-separated)")
    ap.add_argument("--report", action="store_true", help="output a markdown report (for CI job summaries / PR comments)")
    ap.add_argument("--init", action="store_true", help="generate a .driftcheck.toml config file and exit)")
    ap.add_argument("--git-mode", action="store_true", help="only scan files changed since --git-base (default: HEAD~1)")
    ap.add_argument("--git-base", metavar="COMMIT", default="HEAD~1", help="base commit for --git-mode (default: HEAD~1); validated against strict ref format")
    args = ap.parse_args(argv)

    if args.list_detectors:
        _list_detectors()
        return 0

    if args.init:
        _init_config(Path(args.path))
        return 0

    # Git-mode: determine which detectors to run based on changed files
    enabled_detectors = None
    if args.git_mode:
        changed = get_changed_and_untracked(Path(args.path), args.git_base)
        if not changed:
            if not args.quiet:
                print(f"driftcheck: no files changed since {args.git_base}")
            return 0
        enabled_detectors = filter_detectors_by_files(changed, DETECTOR_FILE_PATTERNS)
        if not args.quiet:
            print(f"driftcheck: git-mode — {len(changed)} file(s) changed, {len(enabled_detectors)} detector(s) relevant")

    result = scan_repo(Path(args.path), enabled_detectors=enabled_detectors)

    if args.report:
        _print_report(result)
        blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}
        return 1 if any(blocking.values()) else 0

    # Filter detectors if requested
    if args.only:
        wanted = {d.strip() for d in args.only.split(",")}
        result = {k: v for k, v in result.items() if k in wanted or not k.endswith("_drifts")}
    if args.exclude:
        excluded = {d.strip() for d in args.exclude.split(",")}
        result = {k: v for k, v in result.items() if k not in excluded}

    if args.as_sarif:
        from . import __version__
        sarif_doc = to_sarif(result, version=__version__)
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

    has_blocking = any(blocking_drifts.values())
    has_any_drift = any(all_drifts.values())

    if args.as_json:
        print(json.dumps(result, indent=2))
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
    _print_blocking_drifts(all_drifts, result)
    # Also print informational drifts
    if not args.no_informational:
        _print_informational(all_drifts)
    return 1


def _version() -> str:
    from . import __version__
    return f"%(prog)s {__version__}"


def _init_config(root: Path) -> None:
    """Generate a .driftcheck.toml config file."""
    config_path = root / ".driftcheck.toml"
    if config_path.exists():
        print(f"driftcheck: {config_path} already exists — not overwriting")
        return
    config_path.write_text(
        "[driftcheck]\n"
        "# exclude_detectors = [\"lockfile\", \"nvmrc\"]\n"
        "# fail_on_informational = false\n"
    )
    print(f"driftcheck: created {config_path}")


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
            # Extract actual version from various field names
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
    for d in all_drifts.get("python_drifts", []):
        print(f"driftcheck: {d['file']}: Python {d['doc_version']} → should be {d['pyproject_version']}")
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
