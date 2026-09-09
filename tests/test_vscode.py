"""Tests for VSCode extensions drift detection."""
import tempfile
from pathlib import Path
from driftcheck.detectors.vscode import (
    parse_vscode_extensions,
    find_vscode_extensions_drift,
)


def test_parse_vscode_extensions_basic():
    text = '{"recommendations": ["ms-python.python", "rust-lang.rust-analyzer"]}'
    result = parse_vscode_extensions(text)
    assert result == ["ms-python.python", "rust-lang.rust-analyzer"]


def test_parse_vscode_extensions_empty():
    text = '{"recommendations": []}'
    assert parse_vscode_extensions(text) == []


def test_parse_vscode_extensions_no_recommendations():
    text = '{"settings": {}}'
    assert parse_vscode_extensions(text) == []


def test_find_vscode_extensions_drift_no_drift():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ext_json = '{"recommendations": ["ms-python.python"]}'
        docs = {"README.md": "We recommend the ms-python.python extension"}
        
        drifts = find_vscode_extensions_drift(ext_json, docs)
        assert len(drifts) == 0


def test_find_vscode_extensions_drift_missing():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ext_json = '{"recommendations": ["ms-python.python"]}'
        docs = {"README.md": "We recommend the esbenp.prettier-vscode extension"}
        
        drifts = find_vscode_extensions_drift(ext_json, docs)
        assert len(drifts) == 1
        assert "esbenp.prettier-vscode" in drifts[0]["detail"]


def test_find_vscode_extensions_drift_no_ext_json():
    drifts = find_vscode_extensions_drift(None, {"README.md": "recommend something"})
    assert len(drifts) == 0


def test_vscode_ext_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        vscode_dir = root / ".vscode"
        vscode_dir.mkdir()
        (vscode_dir / "extensions.json").write_text('{"recommendations": ["ms-python.python"]}')
        (root / "README.md").write_text("We recommend esbenp.prettier-vscode")
        
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "vscode_ext_drifts" in result
        assert len(result["vscode_ext_drifts"]) == 1
