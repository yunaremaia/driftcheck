"""Tests for Dart/Flutter drift detection."""
from pathlib import Path
import tempfile

from driftcheck.detectors.dart import (
    parse_dart_sdk_version,
    find_dart_drift,
    DART_SDK_RE,
    DART_DOC_RE,
)
from driftcheck.detector import scan_repo


class TestParseDartSdkVersion:
    def test_constraint_range(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        assert parse_dart_sdk_version(pubspec) == "3.0.0"

    def test_caret_constraint(self):
        pubspec = 'environment:\n  sdk: ^3.2.0'
        assert parse_dart_sdk_version(pubspec) == "3.2.0"

    def test_minimum_only(self):
        pubspec = 'environment:\n  sdk: ">=2.17.0"'
        assert parse_dart_sdk_version(pubspec) == "2.17.0"

    def test_exact_version(self):
        pubspec = 'environment:\n  sdk: "3.0.0"'
        assert parse_dart_sdk_version(pubspec) == "3.0.0"

    def test_no_environment(self):
        pubspec = 'name: my_app\nversion: 1.0.0'
        assert parse_dart_sdk_version(pubspec) is None

    def test_empty(self):
        assert parse_dart_sdk_version("") is None


class TestFindDartDrift:
    def test_no_drift(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        docs = {"README.md": "This project uses Dart 3.0"}
        assert find_dart_drift(pubspec, docs) == []

    def test_drift_major(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        docs = {"README.md": "This project uses Dart 2.17"}
        result = find_dart_drift(pubspec, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "2.17"
        assert result[0]["pubspec_version"] == "3.0.0"

    def test_drift_minor(self):
        pubspec = 'environment:\n  sdk: ">=3.2.0 <4.0.0"'
        docs = {"README.md": "Requires Dart 3.0"}
        result = find_dart_drift(pubspec, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "3.0"

    def test_flutter_mention(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        # Flutter release versions are independent of Dart SDK — should not trigger drift
        docs = {"README.md": "Built with Flutter 3.10 and Dart 3.0"}
        assert find_dart_drift(pubspec, docs) == []

    def test_flutter_drift_not_flagged(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        docs = {"README.md": "Built with Flutter 3.10 and Dart 2.19"}
        # Only Dart version is checked; Flutter is ignored
        result = find_dart_drift(pubspec, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "2.19"

    def test_empty_pubspec(self):
        assert find_dart_drift("", {"README.md": "Dart 3.0"}) == []

    def test_no_docs(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        assert find_dart_drift(pubspec, {}) == []

    def test_toc_numbering_skipped(self):
        pubspec = 'environment:\n  sdk: ">=3.0.0 <4.0.0"'
        docs = {"README.md": "1. Dart 2.0 stuff\n2. Dart 3.0 stuff"}
        assert find_dart_drift(pubspec, docs) == []

    def test_included_in_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pubspec.yaml").write_text('environment:\n  sdk: ">=3.0.0 <4.0.0"')
            (root / "README.md").write_text("This project uses Dart 2.17")
            result = scan_repo(root)
            assert "dart_drifts" in result
            assert len(result["dart_drifts"]) == 1

    def test_no_drift_in_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pubspec.yaml").write_text('environment:\n  sdk: ">=3.0.0 <4.0.0"')
            (root / "README.md").write_text("This project uses Dart 3.0")
            result = scan_repo(root)
            assert "dart_drifts" in result
            assert len(result["dart_drifts"]) == 0
