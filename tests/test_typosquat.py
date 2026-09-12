"""Tests for Typosquat drift detector."""
from pathlib import Path

from driftcheck.detectors.typosquat import (
    find_typosquat_drift,
    _levenshtein,
    _find_suspicious_names,
    KNOWN_PACKAGES,
)


class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("requests", "requests") == 0

    def test_one_edit(self):
        assert _levenshtein("requests", "reqests") == 1

    def test_two_edits(self):
        assert _levenshtein("requests", "rquest") == 2

    def test_empty(self):
        assert _levenshtein("", "requests") == 8

    def test_completely_different(self):
        assert _levenshtein("abc", "xyz") == 3


class TestFindSuspiciousNames:
    def test_no_match(self):
        known = {"requests", "numpy"}
        result = _find_suspicious_names("mytotallyuniquepackage", known)
        assert result == []

    def test_close_match(self):
        known = {"requests", "numpy"}
        result = _find_suspicious_names("reqeusts", known)
        assert "requests" in result

    def test_exact_excluded(self):
        known = {"requests", "numpy"}
        result = _find_suspicious_names("requests", known)
        assert result == []

    def test_numpy_typo(self):
        known = {"numpy"}
        result = _find_suspicious_names("numy", known)
        assert "numpy" in result


class TestFindTyposquatDrift:
    def test_clean_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "requests==2.31.0\nnumpy==1.24.0\nflask==3.0.0\n"
        )
        result = find_typosquat_drift(tmp_path)
        assert result == []

    def test_typosquat_in_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "requests==2.31.0\nreqeusts==2.31.0\nnumpy==1.24.0\n"
        )
        result = find_typosquat_drift(tmp_path)
        assert len(result) >= 1
        assert any("reqeusts" in r["detail"] for r in result)

    def test_clean_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["requests>=2.0", "numpy>=1.24"]\n'
        )
        result = find_typosquat_drift(tmp_path)
        assert result == []

    def test_clean_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"react": "^18.0.0", "lodash": "^4.0.0"}}'
        )
        result = find_typosquat_drift(tmp_path)
        assert result == []

    def test_suspicious_npm_package(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"reacct": "^18.0.0"}}'
        )
        result = find_typosquat_drift(tmp_path)
        assert len(result) >= 1
        assert any("reacct" in r["detail"] for r in result)

    def test_suspicious_cargo_crate(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            '[dependencies]\ntokio = "1.0"\ntokioo = "1.0"\n'
        )
        result = find_typosquat_drift(tmp_path)
        assert len(result) >= 1
        assert any("tokioo" in r["detail"] for r in result)

    def test_no_lockfile(self, tmp_path):
        result = find_typosquat_drift(tmp_path)
        assert result == []

    def test_known_packages_populated(self):
        assert "pypi" in KNOWN_PACKAGES
        assert "npm" in KNOWN_PACKAGES
        assert "crates" in KNOWN_PACKAGES
        assert len(KNOWN_PACKAGES["pypi"]) > 50
        assert len(KNOWN_PACKAGES["npm"]) > 50
        assert len(KNOWN_PACKAGES["crates"]) > 30
