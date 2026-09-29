"""Tests for justfile tool pin drift."""
from driftcheck.detectors.justfile import find_justfile_drift, parse_justfile_versions


JUSTFILE = """
@version python@3.11
node := "node@18"
python := "python3.11"
"""


def test_parse_pins():
    pins = parse_justfile_versions(JUSTFILE)
    assert pins["python"] == "3.11"
    assert pins["node"] == "18"


def test_doc_mismatch():
    docs = {"README.md": "Requires Python 3.10 and Node.js 20.\n"}
    drifts = find_justfile_drift({"justfile": JUSTFILE}, docs)
    tools = {d["tool"] for d in drifts}
    assert tools == {"python", "node"}


def test_aligned_docs():
    docs = {"README.md": "Requires Python 3.11 and Node 18.\n"}
    assert find_justfile_drift({"justfile": JUSTFILE}, docs) == []


def test_ignores_unrelated_assignments():
    text = 'bin := "echo"\n'
    assert parse_justfile_versions(text) == {}


def test_scan_repo_justfile(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "justfile").write_text("@version python@3.10\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Requires Python 3.11.\n", encoding="utf-8")
    result = scan_repo(tmp_path)
    assert any(item["tool"] == "python" for item in result["justfile_drifts"])
