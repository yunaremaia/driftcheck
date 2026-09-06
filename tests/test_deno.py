"""Tests for Deno detector."""
from pathlib import Path
import tempfile

from driftcheck.detectors.deno import (
    parse_deno_version,
    find_deno_drift,
)


class TestParseDenoVersion:
    def test_basic_version(self):
        text = '{"version": "2.0.0"}'
        assert parse_deno_version(text) == "2.0"

    def test_deno_jsonc_with_comments(self):
        text = '// comment\n{"version": "2.1.0"}\n// another'
        assert parse_deno_version(text) == "2.1"

    def test_block_comment(self):
        text = '/* config */\n{"version": "1.40"}'
        assert parse_deno_version(text) == "1.40"

    def test_deno_field(self):
        text = '{"deno": "2.0.0"}'
        assert parse_deno_version(text) == "2.0"

    def test_no_version(self):
        text = '{"name": "my-project"}'
        assert parse_deno_version(text) is None

    def test_empty(self):
        assert parse_deno_version("") is None

    def test_invalid_json(self):
        # Should fall back to regex
        text = 'not json but version: "2.0.0"'
        assert parse_deno_version(text) == "2.0.0"


class TestFindDenoDrift:
    def test_no_drift(self):
        text = '{"version": "2.0.0"}'
        docs = {"README.md": "Requires Deno 2.0"}
        assert find_deno_drift(text, docs) == []

    def test_drift_major(self):
        text = '{"version": "2.0.0"}'
        docs = {"README.md": "Requires Deno 1.40"}
        result = find_deno_drift(text, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "1.40"
        assert result[0]["deno_json_version"] == "2.0"

    def test_drift_minor(self):
        text = '{"version": "2.1.0"}'
        docs = {"README.md": "Requires Deno 2.0"}
        result = find_deno_drift(text, docs)
        assert len(result) == 1

    def test_same_version(self):
        text = '{"version": "2.0.1"}'
        docs = {"README.md": "Requires Deno 2.0"}
        assert find_deno_drift(text, docs) == []

    def test_no_deno_json(self):
        assert find_deno_drift("", {"README.md": "Deno 2.0"}) == []

    def test_drift_in_scan(self):
        import tempfile
        from pathlib import Path
        from driftcheck.detector import scan_repo
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "deno.json").write_text('{"version": "2.0.0"}')
            (root / "README.md").write_text("Requires Deno 1.40 to run")
            result = scan_repo(root)
            assert "deno_drifts" in result
            assert len(result["deno_drifts"]) == 1

    def test_no_drift_in_scan(self):
        import tempfile
        from pathlib import Path
        from driftcheck.detector import scan_repo
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "deno.json").write_text('{"version": "2.0.0"}')
            (root / "README.md").write_text("Requires Deno 2.0")
            result = scan_repo(root)
            assert len(result["deno_drifts"]) == 0
