"""driftcheck CLI."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .detector import scan_repo, apply_fixes
from .sarif import to_sarif

# Drift types that are informational (non-blocking) — reported but don't fail the check
INFORMATIONAL_DRIFTS = {"external_resource_drifts", "dependabot_drifts", "lockfile_drifts", "nvmrc_drifts"}

# All drift type keys — shared across CLI modes
DRIFT_KEYS = [
    "drifts", "rust_drifts", "node_drifts", "bun_drifts", "python_drifts", "go_drifts",
    "count_drifts", "actions_drifts", "lineending_drifts", "docker_drifts",
    "java_drifts", "maven_drifts", "terraform_drifts", "circleci_drifts",
    "gitlab_drifts", "gh_actions_version_drifts", "k8s_drifts", "helm_drifts",
    "dc_drifts", "ci_os_drifts", "dotnet_drifts", "ruby_drifts", "php_drifts",
    "external_resource_drifts", "dependabot_drifts",
    "lockfile_drifts", "tool_versions_drifts", "nvmrc_drifts",
    "swift_drifts",
]

# Detector metadata: key -> (short_name, description)
DETECTOR_INFO = {
    "drifts": ("rust-toolchain", "Rust toolchain.toml channel vs README"),
    "rust_drifts": ("rust-cargo", "Rust Cargo.toml rust-version vs README"),
    "node_drifts": ("node", "Node.js package.json engines vs README"),
    "bun_drifts": ("bun", "Bun package.json engines.bun vs README"),
    "python_drifts": ("python", "Python pyproject.toml requires-python vs README"),
    "go_drifts": ("go", "Go go.mod directive vs README"),
    "docker_drifts": ("docker", "Dockerfile FROM tag vs README"),
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
    "actions_drifts": ("actions-node20", "GitHub Actions Node 20 deprecation"),
    "gh_actions_version_drifts": ("actions-outdated", "GitHub Actions outdated versions"),
    "ci_os_drifts": ("ci-os", "Deprecated CI runner (e.g., ubuntu-20.04)"),
    "lineending_drifts": ("lineending", "Missing .gitattributes line ending config"),
    "count_drifts": ("count", "Skills directory count vs README"),
    "external_resource_drifts": ("external", "External CDN resources in HTML (informational)"),
    "dependabot_drifts": ("dependabot", "Dependabot coverage gaps (informational)"),
    "lockfile_drifts": ("lockfile", "Lockfile missing/stale/orphaned (informational)"),
    "tool_versions_drifts": ("tool-versions", ".tool-versions asdf/mise vs README"),
    "nvmrc_drifts": ("nvmrc", ".nvmrc vs package.json engines (informational)"),
    "swift_drifts": ("swift", "Swift Package.swift version pins vs README"),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="driftcheck",
        description="Detect version drift between docs and toolchain files.",
    )
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    ap.add_argument("--sarif", action="store_true", dest="as_sarif", help="SARIF 2.1.0 output (for GitHub Code Scanning)")
    ap.add_argument("--fix", action="store_true", help="auto-fix detected drifts in documentation files")
    ap.add_argument("--version", action="version", version=_version())
    ap.add_argument("--quiet", "-q", action="store_true", help="only output drifts, suppress OK messages")
    ap.add_argument("--no-informational", action="store_true", help="skip informational drifts in output")
    ap.add_argument("--list-detectors", action="store_true", help="list available detectors and exit")
    ap.add_argument("--only", metavar="DETECTOR", help="run only specified detectors (comma-separated)")
    ap.add_argument("--exclude", metavar="DETECTOR", help="exclude specified detectors (comma-separated)")
    args = ap.parse_args(argv)

    if args.list_detectors:
        _list_detectors()
        return 0

    result = scan_repo(Path(args.path))

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


def _list_detectors() -> None:
    """Print available detectors."""
    print("driftcheck detectors:")
    for key, (short, desc) in DETECTOR_INFO.items():
        blocking = "blocking" if key not in INFORMATIONAL_DRIFTS else "informational"
        print(f"  {short:20s} [{blocking:14s}] {desc}")


def _print_blocking_drifts(all_drifts: dict, result: dict) -> None:
    """Print all blocking drift types."""
    for d in all_drifts.get("drifts", []):
        print(f"driftcheck: {d['file']}: Rust {d['doc_version']} → should be {d['toolchain_version']}")
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
    for d in all_drifts.get("swift_drifts", []):
        print(f"driftcheck: {d['file']}: Swift {d['doc_version']} → should be {d['package_version']} (Package.swift)")


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
