"""driftcheck CLI."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .detector import scan_repo, apply_fixes

# Drift types that are informational (non-blocking) — reported but don't fail the check
INFORMATIONAL_DRIFTS = {"external_resource_drifts", "dependabot_drifts", "lockfile_drifts"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="driftcheck", description="Detect version drift between docs and toolchain.")
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    ap.add_argument("--fix", action="store_true", help="auto-fix detected drifts in documentation files")
    args = ap.parse_args(argv)
    result = scan_repo(Path(args.path))
    
    if args.fix:
        fixed = apply_fixes(Path(args.path), result)
        if fixed:
            print(f"driftcheck: fixed {len(fixed)} file(s): {', '.join(fixed)}")
            return 0
        else:
            print("driftcheck: no drifts to fix")
            return 0
    
    # Collect all drift types
    drift_keys = [
        "drifts", "rust_drifts", "node_drifts", "bun_drifts", "python_drifts", "go_drifts",
        "count_drifts", "actions_drifts", "lineending_drifts", "docker_drifts",
        "java_drifts", "maven_drifts", "terraform_drifts", "circleci_drifts",
        "gitlab_drifts", "gh_actions_version_drifts", "k8s_drifts", "helm_drifts",
        "dc_drifts", "ci_os_drifts", "dotnet_drifts", "ruby_drifts", "php_drifts",
        "external_resource_drifts", "dependabot_drifts",
        "lockfile_drifts",
    ]
    all_drifts = {k: result.get(k, []) for k in drift_keys}
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
        print("driftcheck: no toolchain version found")
        return 0
    
    # No blocking drifts — print OK, then informational drifts
    if not has_blocking:
        parts = []
        if tv: parts.append(f"Rust {tv}")
        if cv: parts.append(f"Rust(Cargo) {cv}")
        if nv: parts.append(f"Node {nv}")
        if pv: parts.append(f"Python {pv}")
        if gv: parts.append(f"Go {gv}")
        base = f"driftcheck: OK — all docs match {' + '.join(parts)}" if parts else "driftcheck: OK"
        print(base)
        _print_informational(all_drifts)
        return 0

    # Print blocking drifts
    _print_blocking_drifts(all_drifts, result)
    # Also print informational drifts
    _print_informational(all_drifts)
    return 1


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


if __name__ == "__main__":
    raise SystemExit(main())
