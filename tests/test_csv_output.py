"""Tests for driftcheck --csv output format."""
import csv
import io
from driftcheck.cli import main


def _capture_csv(args):
    """Run main with --csv and return (exit_code, csv_rows)."""
    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(args)
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    return rc, rows, output


def test_csv_header_only_when_no_drifts(tmp_path):
    """--csv with no drifts outputs header-only CSV."""
    (tmp_path / "README.md").write_text("Hello\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    rc, rows, output = _capture_csv(["--csv", str(tmp_path)])
    assert rc == 0
    assert "file,detector,doc_version,actual_version,severity,message" in output
    assert len(rows) == 0


def test_csv_with_drifts(tmp_path):
    """--csv outputs one row per drift with correct columns."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    rc, rows, output = _capture_csv(["--csv", str(tmp_path)])
    assert rc == 1
    assert len(rows) >= 1
    # Check required columns exist
    row = rows[0]
    assert "file" in row
    assert "detector" in row
    assert "doc_version" in row
    assert "actual_version" in row
    assert "severity" in row
    assert "message" in row


def test_csv_with_actions_drift(tmp_path):
    """--csv outputs GitHub Actions version drift correctly."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: CI\n"
        "on: push\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v5\n"
    )
    (tmp_path / "README.md").write_text("CI\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    rc, rows, output = _capture_csv(["--csv", str(tmp_path)])
    assert rc == 1
    # Should have at least one row for actions drift
    action_rows = [r for r in rows if "actions" in r.get("detector", "")]
    assert len(action_rows) >= 1


def test_csv_quiet_suppresses_header(tmp_path):
    """--csv --quiet outputs no header when no drifts."""
    (tmp_path / "README.md").write_text("Hello\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    rc, rows, output = _capture_csv(["--csv", "--quiet", str(tmp_path)])
    assert rc == 0
    assert len(rows) == 0


def test_csv_no_informational(tmp_path):
    """--csv --no-informational excludes informational drifts."""
    (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=20"}}')
    (tmp_path / "README.md").write_text("Node 20\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    rc, rows, output = _capture_csv(["--csv", "--no-informational", str(tmp_path)])
    assert rc == 0
    # No informational rows
    info_rows = [r for r in rows if r.get("severity") == "informational"]
    assert len(info_rows) == 0
