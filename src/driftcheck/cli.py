"""driftcheck CLI."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .detector import scan_repo

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="driftcheck", description="Detect version drift between docs and toolchain.")
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = ap.parse_args(argv)
    result = scan_repo(Path(args.path))
    drifts = result["drifts"]
    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        if not result["toolchain_version"]:
            print("driftcheck: no rust-toolchain.toml channel found")
            return 0
        if not drifts:
            print(f"driftcheck: OK — all docs match toolchain {result['toolchain_version']}")
            return 0
        print(f"driftcheck: {len(drifts)} drift(s) vs toolchain {result['toolchain_version']}:")
        for d in drifts:
            print(f"  {d['file']}: {d['doc_version']} → should be {d['toolchain_version']}")
    return 1 if drifts else 0

if __name__ == "__main__":
    raise SystemExit(main())
