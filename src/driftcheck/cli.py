"""driftcheck CLI."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .detector import scan_repo, apply_fixes

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
    
    if args.as_json:
        print(json.dumps(result, indent=2))
        has_blocking = (result.get("drifts") or result.get("rust_drifts") or result.get("node_drifts") or result.get("python_drifts") or result.get("go_drifts") or result.get("count_drifts") or result.get("actions_drifts") or result.get("lineending_drifts") or result.get("docker_drifts") or result.get("java_drifts"))
        return 1 if has_blocking else 0
    
    drifts = result.get("drifts", [])
    rust_drifts = result.get("rust_drifts", [])
    node_drifts = result.get("node_drifts", [])
    python_drifts = result.get("python_drifts", [])
    go_drifts = result.get("go_drifts", [])
    count_drifts = result.get("count_drifts", [])
    actions_drifts = result.get("actions_drifts", [])
    lineending_drifts = result.get("lineending_drifts", [])
    external_resource_drifts = result.get("external_resource_drifts", [])
    docker_drifts = result.get("docker_drifts", [])
    java_drifts = result.get("java_drifts", [])
    maven_drifts = result.get("maven_drifts", [])
    terraform_drifts = result.get("terraform_drifts", [])
    circleci_drifts = result.get("circleci_drifts", [])
    gitlab_drifts = result.get("gitlab_drifts", [])
    tv = result.get("toolchain_version")
    cv = result.get("cargo_rust_version")
    nv = result.get("package_node")
    pv = result.get("pyproject_python")
    gv = result.get("gomod_version")
    
    if not tv and not cv and not nv and not pv and not gv and not count_drifts and not actions_drifts and not lineending_drifts and not external_resource_drifts and not docker_drifts and not java_drifts and not maven_drifts and not terraform_drifts and not circleci_drifts and not gitlab_drifts:
        print("driftcheck: no toolchain version found")
        return 0
    
    if not drifts and not rust_drifts and not node_drifts and not python_drifts and not go_drifts and not count_drifts and not actions_drifts and not lineending_drifts and not docker_drifts and not java_drifts and not maven_drifts and not terraform_drifts and not circleci_drifts and not gitlab_drifts:
        parts = []
        if tv: parts.append(f"Rust {tv}")
        if cv: parts.append(f"Rust(Cargo) {cv}")
        if nv: parts.append(f"Node {nv}")
        if pv: parts.append(f"Python {pv}")
        if gv: parts.append(f"Go {gv}")
        base = f"driftcheck: OK — all docs match {' + '.join(parts)}" if parts else "driftcheck: OK"
        if external_resource_drifts:
            print(base)
            for d in external_resource_drifts:
                print(f"driftcheck: info: {d['file']}: {d['detail']} ({d['url']})")
            return 0
        print(base)
        return 0

    for d in drifts:
        print(f"driftcheck: {d['file']}: Rust {d['doc_version']} → should be {d['toolchain_version']}")
    for d in rust_drifts:
        target = d.get("toolchain_version") or d.get("cargo_version")
        print(f"driftcheck: {d['file']}: Rust {d['doc_version']} → should be {target}")
    for d in node_drifts:
        print(f"driftcheck: {d['file']}: Node {d['doc_version']} → should be {d['package_version']}")
    for d in python_drifts:
        print(f"driftcheck: {d['file']}: Python {d['doc_version']} → should be {d['pyproject_version']}")
    for d in go_drifts:
        print(f"driftcheck: {d['file']}: Go {d['doc_version']} → should be {d['gomod_version']}")
    for d in count_drifts:
        print(f"driftcheck: {d['file']}: {d['doc_count']} skills → should be {d['actual_count']} (skills/ count)")
    for d in actions_drifts:
        print(f"driftcheck: {d['file']}: {d['action']}@{d['current']} → should be {d['suggested']} (node20→node24)")
    for d in lineending_drifts:
        print(f"driftcheck: {d['file']}: {d['detail']}")
    for d in external_resource_drifts:
        print(f"driftcheck: info: {d['file']}: {d['detail']} ({d['url']})")
    for d in docker_drifts:
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['dockerfile_image']} (Dockerfile)")
    for d in java_drifts:
        print(f"driftcheck: {d['file']}: Java {d['doc_version']} → should be {d['gradle_version']} (build.gradle)")
    for d in maven_drifts:
        print(f"driftcheck: {d['file']}: Java {d['doc_version']} → should be {d['maven_version']} (pom.xml)")
    for d in terraform_drifts:
        print(f"driftcheck: {d['file']}: Terraform {d['provider']} {d['doc_version']} → should be {d['terraform_version']}")
    for d in circleci_drifts:
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['circleci_image']} (CircleCI)")
    for d in gitlab_drifts:
        print(f"driftcheck: {d['file']}: {d['doc_image']} → should be {d['gitlab_image']} (GitLab CI)")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())