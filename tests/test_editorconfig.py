"""Tests for EditorConfig drift detection."""
import tempfile
from pathlib import Path
from driftcheck.detectors.editorconfig import (
    parse_editorconfig,
    find_editorconfig_drift,
)


def test_parse_editorconfig_basic():
    config = """root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
"""
    result = parse_editorconfig(config)
    assert result == {
        "root": "true",
        "indent_style": "space",
        "indent_size": "4",
        "end_of_line": "lf",
        "charset": "utf-8",
    }


def test_parse_editorconfig_empty():
    assert parse_editorconfig("") == {}


def test_find_editorconfig_drift_no_drift():
    config = """root = true

[*]
indent_size = 4
indent_style = space
"""
    docs = {"README.md": "Uses 4 spaces for indentation"}
    
    drifts = find_editorconfig_drift(config, docs)
    assert len(drifts) == 0


def test_find_editorconfig_drift_indent_size():
    config = """root = true

[*]
indent_size = 2
"""
    docs = {"README.md": "Uses 4 spaces for indentation"}
    
    drifts = find_editorconfig_drift(config, docs)
    assert len(drifts) == 1
    assert "indent_size=2" in drifts[0]["detail"]
    assert "4" in drifts[0]["detail"]


def test_find_editorconfig_drift_indent_style():
    config = """root = true

[*]
indent_style = space
"""
    docs = {"README.md": "Use tabs only for indent"}
    
    drifts = find_editorconfig_drift(config, docs)
    assert len(drifts) == 1
    assert "indent_style=space" in drifts[0]["detail"]
    assert "tabs" in drifts[0]["detail"]


def test_find_editorconfig_drift_line_ending():
    config = """root = true

[*]
end_of_line = lf
"""
    docs = {"README.md": "Line ending is crlf"}
    
    drifts = find_editorconfig_drift(config, docs)
    assert len(drifts) == 1
    assert "end_of_line=lf" in drifts[0]["detail"]


def test_find_editorconfig_drift_vscode():
    config = """root = true

[*]
indent_size = 2
"""
    docs = {"README.md": "No mentions"}
    vscode = '{"tabSize": 4}'
    
    drifts = find_editorconfig_drift(config, docs, vscode)
    assert len(drifts) == 1
    assert "indent_size=2" in drifts[0]["detail"]
    assert "tabSize=4" in drifts[0]["detail"]


def test_find_editorconfig_drift_no_config():
    assert find_editorconfig_drift(None, {"README.md": "text"}) == []


def test_editorconfig_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".editorconfig").write_text("""root = true

[*]
indent_size = 4
""")
        (root / "README.md").write_text("Uses 2 spaces")
        
        from driftcheck.detector import scan_repo
        result = scan_repo(root)
        assert "editorconfig_drifts" in result
        assert len(result["editorconfig_drifts"]) == 1
