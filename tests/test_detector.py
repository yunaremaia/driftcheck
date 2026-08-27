"""TDD for driftcheck — RED first, then GREEN."""

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

from driftcheck.detector import parse_cargo_rust_version, find_rust_drift_multi

def test_cargo_rust_version_parse():
    assert parse_cargo_rust_version('rust-version = "1.96.1"\n') == "1.96.1"
    assert parse_cargo_rust_version('rust-version = "1.96"\n') == "1.96"
    assert parse_cargo_rust_version('[package]\nversion = "0.1"\n') is None

def test_rust_drift_multi_cargo_source():
    cargo = 'rust-version = "1.96.1"\n'
    docs = {"README.md": "Build with Rust 1.90.0"}
    drifts = find_rust_drift_multi(toolchain_text="", cargo_text=cargo, docs=docs)
    assert len(drifts) == 1
    assert drifts[0]["cargo_version"] == "1.96.1"

def test_rust_drift_multi_channel_without_patch():
    toolchain = 'channel = "1.96"\n'
    docs = {"README.md": "Rust 1.96.1"}
    assert find_rust_drift_multi(toolchain_text=toolchain, cargo_text="", docs=docs) == []

def test_rust_drift_multi_minor_mismatch():
    toolchain = 'channel = "1.96"\n'
    docs = {"README.md": "Rust 1.90 required"}
    drifts = find_rust_drift_multi(toolchain_text=toolchain, cargo_text="", docs=docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "1.90"


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


from driftcheck.detector import find_python_drift

def test_python_no_drift():
    pkg = 'requires-python = ">=3.10"'
    docs = {"README.md": "Python 3.10+"}
    assert find_python_drift(pkg, docs) == []

def test_python_detects_drift():
    pkg = 'requires-python = ">=3.12"'
    docs = {"README.md": "Python 3.10+"}
    drifts = find_python_drift(pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "3.10"
    assert drifts[0]["pyproject_version"] == "3.12"


from driftcheck.detector import find_go_drift, parse_go_version_from_gomod

def test_go_no_drift():
    gomod = "module example.com/foo\n\ngo 1.23\n"
    docs = {"README.md": "Requires Go 1.23"}
    assert find_go_drift(gomod, docs) == []

def test_go_detects_drift():
    gomod = "module example.com/foo\n\ngo 1.23\n"
    docs = {"README.md": "Requires Go 1.21"}
    drifts = find_go_drift(gomod, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "1.21"
    assert drifts[0]["gomod_version"] == "1.23"

def test_parse_go_version_from_gomod_missing():
    assert parse_go_version_from_gomod("module foo\n") is None


from driftcheck.detector import apply_fixes

def test_apply_fixes_rewrites_doc_to_match_toolchain():
    from pathlib import Path
    import tempfile
    result = {
        "drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1"}],
        "node_drifts": [{"file": "CONTRIBUTING.md", "doc_version": "18", "package_version": "24"}],
        "python_drifts": [{"file": "docs/README.md", "doc_version": "3.10", "pyproject_version": "3.12"}],
        "go_drifts": [{"file": "README.md", "doc_version": "1.21", "gomod_version": "1.23"}],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("Rust 1.93.0 and Go 1.21 here")
        (root / "CONTRIBUTING.md").write_text("Use Node.js 18 please")
        (root / "docs").mkdir()
        (root / "docs" / "README.md").write_text("Python 3.10 required")
        fixed = apply_fixes(root, result)
        assert set(fixed) == {"README.md", "CONTRIBUTING.md", "docs/README.md"}
        assert "Rust 1.96.1" in (root / "README.md").read_text()
        assert "Go 1.23" in (root / "README.md").read_text()
        assert "Node.js 24" in (root / "CONTRIBUTING.md").read_text()
        assert "Python 3.12" in (root / "docs" / "README.md").read_text()


def test_apply_fixes_idempotent_when_no_drift():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("Rust 1.96.1")
        fixed = apply_fixes(root, {"drifts": [], "node_drifts": [], "python_drifts": [], "go_drifts": []})
        assert fixed == []
