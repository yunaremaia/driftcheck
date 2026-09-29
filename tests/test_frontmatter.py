"""Tests for Markdown YAML frontmatter drift."""
from driftcheck.detectors.frontmatter import find_frontmatter_drift, parse_frontmatter

README = """---
version: 1.2.3
rust_version: "1.78"
python_version: "3.11"
license: MIT
---

# Demo
"""


def test_parse_frontmatter():
    fields = parse_frontmatter(README)
    assert fields["version"] == "1.2.3"
    assert fields["rust_version"] == "1.78"
    assert "license" in fields


def test_no_frontmatter():
    assert parse_frontmatter("# Hello\n") == {}


def test_version_and_toolchain_drift():
    docs = {"README.md": README}
    drifts = find_frontmatter_drift(
        docs,
        cargo_text='[package]\nversion = "1.3.0"\nrust-version = "1.80"\n',
        pyproject_text='[project]\nrequires-python = ">=3.12"\n',
    )
    tools = {item["tool"] for item in drifts}
    assert "version" in tools
    assert "Rust" in tools
    assert "Python" in tools


def test_matching_frontmatter_is_quiet():
    docs = {"README.md": "---\npython_version: 3.11\n---\n"}
    assert find_frontmatter_drift(
        docs,
        pyproject_text='[project]\nrequires-python = ">=3.11"\n',
    ) == []


def test_scan_repo_frontmatter(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "README.md").write_text('---\npython_version: "3.10"\n---\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n', encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["tool"] == "Python" for item in result["frontmatter_drifts"])
