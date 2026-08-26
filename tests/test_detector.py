"""TDD for driftcheck — RED first."""

from driftcheck.detector import find_rust_drift

def test_no_drift():
    toolchain = 'channel = "1.96.1"'
    docs = {"README.md": "Install Rust 1.96.1", "docs/README.zh-CN.md": "Rust 1.96.1"}
    assert find_rust_drift(toolchain, docs) == []

def test_detects_drift():
    toolchain = 'channel = "1.96.1"'
    docs = {"README.md": "Install Rust 1.93.0", "docs/README.de.md": "Rust 1.96.1"}
    drifts = find_rust_drift(toolchain, docs)
    assert len(drifts) == 1
    assert drifts[0]["file"] == "README.md"
    assert drifts[0]["doc_version"] == "1.93.0"
    assert drifts[0]["toolchain_version"] == "1.96.1"

def test_no_toolchain_returns_empty():
    assert find_rust_drift("", {"README.md": "Rust 1.93.0"}) == []

def test_scan_repo():
    from pathlib import Path
    import tempfile
    from driftcheck.detector import scan_repo
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (root / "README.md").write_text("Install Rust 1.93.0")
        result = scan_repo(root)
        assert result["toolchain_version"] == "1.96.1"
        assert len(result["drifts"]) == 1

from driftcheck.detector import find_node_drift

def test_node_no_drift():
    pkg = '{"engines": {"node": "24.x"}}'
    docs = {"README.md": "Install Node.js 24"}
    assert find_node_drift(pkg, docs) == []

def test_node_detects_drift():
    pkg = '{"engines": {"node": "24.x"}}'
    docs = {"README.md": "Install Node.js 18"}
    drifts = find_node_drift(pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "18"
    assert drifts[0]["package_version"] == "24"
