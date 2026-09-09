"""Tests for Gradle Version Catalog drift detection: libs.versions.toml vs README."""
from pathlib import Path
import tempfile

from driftcheck.detectors.gradle_catalog import (
    parse_gradle_catalog,
    find_gradle_catalog_drift,
)


class TestParseGradleCatalog:
    def test_empty_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\n')
            result = parse_gradle_catalog(path)
            assert result == {}

    def test_missing_file(self):
        result = parse_gradle_catalog(Path("/nonexistent/libs.versions.toml"))
        assert result == {}

    def test_basic_versions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\njava = "17"\njunit = "5.10"\n')
            result = parse_gradle_catalog(path)
            assert result.get("java") == "17"
            assert result.get("junit") == "5.10"

    def test_library_version_entries(self):
        """Test parsing library entries with { module = ..., version = ... } format."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text(
                '[versions]\njunit = "5.10"\n[libraries]\ntest-junit = { module = "junit:junit", version = "5.10" }\n'
            )
            result = parse_gradle_catalog(path)
            assert result.get("junit") == "5.10"
            assert result.get("test-junit") == "5.10"


class TestFindGradleCatalogDrift:
    def test_no_catalog(self, tmp_path):
        assert find_gradle_catalog_drift(tmp_path) == []

    def test_drift_detected(self, tmp_path):
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\njava = "17"\n')
        readme = tmp_path / "README.md"
        readme.write_text("Requires Java 11")
        drifts = find_gradle_catalog_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(d.get("catalog_version") == "17" for d in drifts)

    def test_no_drift(self, tmp_path):
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\njava = "17"\n')
        readme = tmp_path / "README.md"
        readme.write_text("Requires Java 17")
        drifts = find_gradle_catalog_drift(tmp_path)
        # Should not detect drift when versions match
        assert len(drifts) == 0

    def test_no_readme(self, tmp_path):
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\njava = "17"\n')
        assert find_gradle_catalog_drift(tmp_path) == []

    def test_root_level_catalog(self, tmp_path):
        catalog = tmp_path / "libs.versions.toml"
        catalog.write_text('[versions]\njava = "17"\n')
        readme = tmp_path / "README.md"
        readme.write_text("Requires Java 11")
        drifts = find_gradle_catalog_drift(tmp_path)
        assert len(drifts) >= 1
