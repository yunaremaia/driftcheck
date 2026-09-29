"""Tests for go.mod require/replace/exclude vs go.sum."""
from driftcheck.detectors.go_replace import find_go_replace_drift, parse_go_requires

GOMOD = """
module example.com/demo

go 1.22

require (
    github.com/foo/bar v1.2.3
    github.com/baz/qux v1.0.0 // indirect
)

require github.com/solo/mod v0.4.0

replace github.com/foo/bar => github.com/foo/bar v1.2.4

replace github.com/local/mod => ../local

exclude github.com/baz/qux v1.0.0
"""

SUM = """
github.com/foo/bar v1.2.3 h1:abc
github.com/foo/bar v1.2.3/go.mod h1:def
github.com/other/mod v9.9.9 h1:zzz
"""


def test_parse_requires_from_block_and_line():
    requires = parse_go_requires(GOMOD)
    assert requires["github.com/foo/bar"] == "v1.2.3"
    assert requires["github.com/baz/qux"] == "v1.0.0"
    assert requires["github.com/solo/mod"] == "v0.4.0"


def test_missing_sum_version_replace_and_exclude():
    drifts = find_go_replace_drift(GOMOD, SUM)
    details = " ".join(item["detail"] for item in drifts)
    assert "github.com/baz/qux" in details
    assert "missing from go.sum" in details or "go.sum has" in details
    assert "replaced with v1.2.4" in details
    assert "excluded" in details
    assert "../local" not in details
    assert "github.com/foo/bar v1.2.3 is required" not in details or "replaced" in details


def test_aligned_sum_is_quiet():
    gomod = "require github.com/foo/bar v1.2.3\n"
    gosum = "github.com/foo/bar v1.2.3 h1:abc\n"
    assert find_go_replace_drift(gomod, gosum) == []


def test_missing_sum_file_is_quiet():
    assert find_go_replace_drift(GOMOD, "") == []


def test_scan_repo_go_replace(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "go.mod").write_text("require github.com/foo/bar v1.2.3\n", encoding="utf-8")
    (tmp_path / "go.sum").write_text("github.com/foo/bar v1.2.4 h1:abc\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["package"] == "github.com/foo/bar" for item in result["go_replace_drifts"])
