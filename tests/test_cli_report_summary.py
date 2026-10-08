"""Tests for driftcheck --report statistical summary feature."""
from driftcheck.cli import main


def test_report_summary_blocking_only(tmp_path, capsys):
    """--report shows summary with blocking drifts only."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "## driftcheck report" in captured.out
    assert "### 📊 Summary" in captured.out
    assert "**Total drifts:**" in captured.out
    assert "Blocking:" in captured.out


def test_report_summary_informational_only(tmp_path, capsys):
    """--report shows summary with informational drifts only."""
    (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=20"}, "dependencies": {"lodash": "^4.0.0"}}')
    (tmp_path / "README.md").write_text("Node 20\nlodash 4.17.0\n")
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "### 📊 Summary" in captured.out
    assert "Informational:" in captured.out


def test_report_summary_no_drifts(tmp_path, capsys):
    """--report with no drifts shows success message, no summary block."""
    (tmp_path / "README.md").write_text("Hello\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "### 📊 Summary" not in captured.out
    assert "✅ No drift" in captured.out


def test_report_summary_detector_breakdown(tmp_path, capsys):
    """--report shows detector breakdown when multiple detectors fire."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\nNode 20\n")
    (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=22"}}')
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "### 📊 Summary" in captured.out
    assert "Detectors fired:" in captured.out
    assert "`makefile`" in captured.out or "`node`" in captured.out


def test_report_summary_top_files(tmp_path, capsys):
    """--report shows top files with most drifts."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\nCMAKE_VERSION = 3.28\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\nCMake 3.27\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "Top files:" in captured.out
    assert "README.md" in captured.out


def test_report_summary_total_count(tmp_path, capsys):
    """--report counts total drifts correctly."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\nNode 20\n")
    (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=22"}}')
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    # At least 2 blocking drifts (gcc + node)
    assert "**Total drifts:**" in captured.out
    # Verify the count is at least 2
    import re
    m = re.search(r'\*\*Total drifts:\*\* (\d+)', captured.out)
    assert m is not None
    total = int(m.group(1))
    assert total >= 2


def test_report_summary_backward_compat(tmp_path, capsys):
    """Existing per-drift output format is preserved with summary added."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    # Summary is present
    assert "### 📊 Summary" in captured.out
    # Original per-drift detail still present
    assert "### ❌ Blocking drifts" in captured.out
    assert "GCC" in captured.out
