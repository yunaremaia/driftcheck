"""Tests for Kotlin Multiplatform (KMP) version catalog drift detection."""

import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.kotlin_multiplatform import (
    BADGE_RES,
    KMP_VERSION_KEYS,
    find_kotlin_multiplatform_drift,
    parse_kmp_versions,
)


class TestParseKmpVersions:
    """Tests for parse_kmp_versions function."""

    def test_empty_file(self):
        """Empty file returns empty dict."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text("")
            result = parse_kmp_versions(str(path))
            assert result == {}

    def test_missing_file(self):
        """Missing file returns empty dict."""
        result = parse_kmp_versions("/nonexistent/libs.versions.toml")
        assert result == {}

    def test_only_non_kmp_keys(self):
        """File with no KMP keys returns them all (filtering happens later)."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\njunit = "5.10"\njackson = "2.15"\n')
            result = parse_kmp_versions(str(path))
            assert result.get("junit") == "5.10"
            assert result.get("jackson") == "2.15"

    def test_kotlin_version(self):
        """Extract kotlin version from [versions] section."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\nkotlin = "2.0.0"\n')
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin") == "2.0.0"

    def test_kotlin_coroutines_version(self):
        """Extract kotlin-coroutines version."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\nkotlin-coroutines = "1.8.0"\n')
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin-coroutines") == "1.8.0"

    def test_compose_bom_version(self):
        """Extract compose-bom version."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\ncompose-bom = "2024.01.00"\n')
            result = parse_kmp_versions(str(path))
            assert result.get("compose-bom") == "2024.01.00"

    def test_kgp_version(self):
        """Extract kgp (Kotlin Gradle Plugin) version."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text('[versions]\nkgp = "2.0.0"\n')
            assert parse_kmp_versions(str(path)).get("kgp") == "2.0.0"

    def test_multiple_kmp_versions(self):
        """Extract multiple KMP versions from same file."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text(
                '[versions]\n'
                'kotlin = "2.0.0"\n'
                'kotlin-coroutines = "1.8.0"\n'
                'compose-bom = "2024.01.00"\n'
                'kgp = "2.0.0"\n'
                'agp = "8.2.0"\n'
                'ksp = "2.0.0-1.0.20"\n'
            )
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin") == "2.0.0"
            assert result.get("kotlin-coroutines") == "1.8.0"
            assert result.get("compose-bom") == "2024.01.00"
            assert result.get("kgp") == "2.0.0"
            assert result.get("agp") == "8.2.0"
            assert result.get("ksp") == "2.0.0-1.0.20"

    def test_plugins_section_with_versions(self):
        """Parse plugins section for versioned plugins."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text(
                '[versions]\n'
                'kotlin = "2.0.0"\n'
                '[plugins]\n'
                'kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version = "2.0.0" }\n'
            )
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin") == "2.0.0"
            assert result.get("kotlin-jvm") == "2.0.0"

    def test_ignores_comments(self):
        """Comments in [versions] section are ignored."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text(
                '[versions]\n'
                '# kotlin version\n'
                'kotlin = "2.0.0"\n'
            )
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin") == "2.0.0"
            assert "#" not in result

    def test_ignores_libraries_section(self):
        """Library declarations without KMP keys are parsed but filtered later."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libs.versions.toml"
            path.write_text(
                '[versions]\n'
                'kotlin = "2.0.0"\n'
                '[libraries]\n'
                'core-ktx = { module = "androidx.core:core-ktx", version = "1.12.0" }\n'
            )
            result = parse_kmp_versions(str(path))
            assert result.get("kotlin") == "2.0.0"
            # Library entries are not parsed by parse_kmp_versions (no version key at top level)


class TestFindKotlinMultiplatformDrift:
    """Tests for find_kotlin_multiplatform_drift function."""

    def test_no_catalog(self, tmp_path):
        """Returns empty list when no libs.versions.toml exists."""
        readme = tmp_path / "README.md"
        readme.write_text("Built with Kotlin 2.0")
        assert find_kotlin_multiplatform_drift(tmp_path) == []

    def test_no_readme(self, tmp_path):
        """Returns empty list when README doesn't exist."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\nkotlin = "2.0.0"\n')
        assert find_kotlin_multiplatform_drift(tmp_path) == []

    def test_no_kmp_keys(self, tmp_path):
        """Returns empty list when catalog has no KMP keys."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\njunit = "5.10"\n')
        readme = tmp_path / "README.md"
        readme.write_text("Built with Kotlin 2.0")
        assert find_kotlin_multiplatform_drift(tmp_path) == []

    def test_kotlin_badge_drift(self, tmp_path):
        """Detects drift between catalog kotlin version and README badge."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\nkotlin = "2.0.0"\n')
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-1.9.22-blue)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(
            d.get("library") == "kotlin"
            and d.get("catalog_version") == "2.0.0"
            and d.get("readme_version") == "1.9.22"
            for d in drifts
        )

    def test_kotlin_badge_no_drift(self, tmp_path):
        """No drift when catalog and README badge match."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\nkotlin = "2.0.0"\n')
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-2.0.0-blue)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) == 0

    def test_kotlin_minor_mismatch_detected(self, tmp_path):
        """Detects drift when only minor version differs."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\nkotlin = "2.1.0"\n')
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-2.0.0-blue)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(d.get("library") == "kotlin" for d in drifts)

    def test_compose_bom_drift(self, tmp_path):
        """Detects drift in compose-bom version."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\ncompose-bom = "2024.02.00"\n')
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Compose](https://img.shields.io/badge/Compose-2024.01.00-green)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) >= 1
        assert any(d.get("library") == "compose-bom" for d in drifts)

    def test_multiple_drifts(self, tmp_path):
        """Detects drift in multiple KMP versions simultaneously."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            '[versions]\n'
            'kotlin = "2.0.0"\n'
            'compose-bom = "2024.02.00"\n'
        )
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-1.9.22-blue)\n"
            "![Compose](https://img.shields.io/badge/Compose-2024.01.00-green)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        libraries = {d.get("library") for d in drifts}
        assert "kotlin" in libraries
        assert "compose-bom" in libraries

    def test_root_level_catalog(self, tmp_path):
        """Catalog at repo root (not in gradle/) is found."""
        catalog = tmp_path / "libs.versions.toml"
        catalog.write_text('[versions]\nkotlin = "2.0.0"\n')
        readme = tmp_path / "README.md"
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-1.9.22-blue)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) >= 1

    def test_kmp_version_keys_constant(self):
        """KMP_VERSION_KEYS contains expected keys."""
        expected = {"kotlin", "kotlin-coroutines", "compose-bom", "compose-compiler", "kgp", "agp", "ksp"}
        assert set(KMP_VERSION_KEYS) == expected

    def test_badge_patterns_exist_for_all_keys(self):
        """Every KMP key has a corresponding badge pattern."""
        for key in KMP_VERSION_KEYS:
            assert key in BADGE_RES, f"Missing badge pattern for key: {key}"

    def test_compose_bom_exact_match(self, tmp_path):
        """Compose BOM uses exact version comparison (no tolerance)."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\ncompose-bom = "2024.01.00"\n')
        readme = tmp_path / "README.md"
        # Different patch version should be flagged
        readme.write_text(
            "![Compose](https://img.shields.io/badge/Compose-2024.01.01-green)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert any(d.get("library") == "compose-bom" for d in drifts)

    def test_kotlin_patch_tolerance(self, tmp_path):
        """Kotlin versions with same major.minor but different patch are not flagged."""
        catalog = tmp_path / "gradle" / "libs.versions.toml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('[versions]\nkotlin = "2.0.21"\n')
        readme = tmp_path / "README.md"
        # Same major.minor, different patch — should NOT be flagged
        readme.write_text(
            "![Kotlin](https://img.shields.io/badge/Kotlin-2.0.0-blue)\n"
        )
        drifts = find_kotlin_multiplatform_drift(tmp_path)
        assert len(drifts) == 0
