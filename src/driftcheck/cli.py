"""driftcheck CLI."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .detector import scan_repo

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="driftcheck", description="Detect version drift between docs and toolchain.")
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = ap.parse_args(argv)
    result = scan_repo(Path(args.path))
    if args.as_json:
        print(json.dumps(result, indent=2))
        return 1 if (result.get("drifts") or result.get("node_drifts")) else 0
    drifts = result.get("drifts", [])
    node_drifts = result.get("node_drifts", [])
    tv = result.get("toolchain_version")
    nv = result.get("package_node")
    if not tv and not nv:
        print("driftcheck: no toolchain version found (rust-toolchain.toml or package.json)")
        return 0
    if not drifts and not node_drifts:
        parts = []
        if tv: parts.append(f"Rust {tv}")
        if nv: parts.append(f"Node {nv}")
        print(f"driftcheck: OK — all docs match {' + '.join(parts)}")
        return 0
    for d in drifts:
        print(f"driftcheck: {d['file']}: Rust {d['doc_version']} → should be {d['toolchain_version']}")
    for d in node_drifts:
        print(f"driftcheck: {d['file']}: Node {d['doc_version']} → should be {d['package_version']}")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
