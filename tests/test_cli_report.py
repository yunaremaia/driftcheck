"""Tests for driftcheck --init and --report CLI features."""
import io
import sys
from pathlib import Path
from driftcheck.cli import main


def test_init_creates_config(tmp_path):
    """--init creates a .driftcheck.toml file."""
    result = main(["--init", str(tmp_path)])
    config = tmp_path / ".driftcheck.toml"
    assert config.exists()
    assert result == 0
    content = config.read_text()
    assert "[driftcheck]" in content


def test_init_does_not_overwrite(tmp_path, capsys):
    """--init does not overwrite an existing config."""
    config = tmp_path / ".driftcheck.toml"
    config.write_text("# existing config\n")
    result = main(["--init", str(tmp_path)])
    assert config.read_text() == "# existing config\n"
    assert result == 0


def test_report_no_drifts(tmp_path, capsys):
    """--report prints success message when no drifts."""
    (tmp_path / "README.md").write_text("Hello\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 0
    captured = capsys.readouterr()
    assert "No drift" in captured.out


def test_report_with_drifts(tmp_path, capsys):
    """--report prints markdown report with drifts."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 1
    captured = capsys.readouterr()
    assert "## driftcheck report" in captured.out
    assert "GCC" in captured.out
    assert "Blocking drifts" in captured.out


def test_report_with_informational(tmp_path, capsys):
    """--report shows informational drifts when present."""
    (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=20"}}')
    (tmp_path / "README.md").write_text("Node 20\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 0  # Node 20 matches engines.node ">=20"
    captured = capsys.readouterr()
    assert "driftcheck report" in captured.out


def test_report_exit_code_blocking(tmp_path):
    """--report exits with 1 for blocking drifts."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 1


def test_report_exit_code_clean(tmp_path):
    """--report exits with 0 when clean."""
    (tmp_path / "README.md").write_text("Nothing here\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 0


def test_report_with_init(tmp_path, capsys):
    """--init followed by --report works correctly."""
    result = main(["--init", str(tmp_path)])
    assert result == 0
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    result = main(["--report", str(tmp_path)])
    assert result == 0


def test_report_lists_file_paths(tmp_path, capsys):
    """--report includes file paths in output."""
    (tmp_path / "Makefile").write_text("GCC_VERSION = 14.1.0\n")
    (tmp_path / "README.md").write_text("Requires GCC 13\n")
    result = main(["--report", str(tmp_path)])
    captured = capsys.readouterr()
    assert "README.md" in captured.out
