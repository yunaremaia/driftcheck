"""Tests for custom doc_paths configuration."""
import tempfile
from pathlib import Path
from driftcheck.detector import scan_repo


def test_custom_doc_paths():
    """Test that custom doc_paths from config are included in scanning."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Create a custom doc file
        (root / "CUSTOM.md").write_text("Requires Ruby 3.2.2")
        (root / ".ruby-version").write_text("3.1.0")
        (root / "README.md").write_text("No version mentioned here")
        
        # Without custom doc_paths, no drift should be detected
        result = scan_repo(root)
        assert len(result.get("ruby_version_drifts", [])) == 0
        
        # With custom doc_paths, drift should be detected
        import os
        os.environ["DRIFTCHECK_CONFIG"] = str(root / ".driftcheck.toml")
        (root / ".driftcheck.toml").write_text(
            '[driftcheck]\ndoc_paths = ["CUSTOM.md"]\n'
        )
        result = scan_repo(root)
        assert len(result.get("ruby_version_drifts", [])) == 1
        assert result["ruby_version_drifts"][0]["file"] == "CUSTOM.md"
        
        del os.environ["DRIFTCHECK_CONFIG"]


def test_custom_doc_paths_glob():
    """Test that glob patterns work in doc_paths."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs_dir = root / "documentation"
        docs_dir.mkdir()
        (docs_dir / "setup.md").write_text("Requires Python 3.10")
        (root / ".python-version").write_text("3.11.5")
        (root / "README.md").write_text("No version mentioned")
        
        (root / ".driftcheck.toml").write_text(
            '[driftcheck]\ndoc_paths = ["documentation/*.md"]\n'
        )
        result = scan_repo(root)
        assert len(result.get("python_version_drifts", [])) == 1
