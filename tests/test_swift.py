"""Tests for Swift Package Manager detector."""
from pathlib import Path
import tempfile

from driftcheck.detectors.swift import (
    parse_swift_version_from_package,
    find_swift_drift,
)


class TestParseSwiftVersion:
    def test_swift_tools_version(self):
        text = "// swift-tools-version:5.9\nimport PackageDescription"
        assert parse_swift_version_from_package(text) == "5.9"

    def test_swift_tools_version_with_patch(self):
        text = "// swift-tools-version:5.9.0\nimport PackageDescription"
        assert parse_swift_version_from_package(text) == "5.9.0"

    def test_dependency_from_version(self):
        text = """
// swift-tools-version:5.9
import PackageDescription
let Package = Package(
    name: "Test",
    dependencies: [
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.0.0"),
    ]
)
"""
        assert parse_swift_version_from_package(text) == "5.9"

    def test_no_version(self):
        assert parse_swift_version_from_package("") is None

    def test_no_swift_directive(self):
        text = "// Some other comment\nimport PackageDescription"
        # Falls back to dependency version
        assert parse_swift_version_from_package(text) is None


class TestFindSwiftDrift:
    def test_no_drift(self):
        pkg = "// swift-tools-version:5.9\nimport PackageDescription"
        docs = {"README.md": "This project requires Swift 5.9"}
        assert find_swift_drift(pkg, docs) == []

    def test_drift_major(self):
        pkg = "// swift-tools-version:5.9\nimport PackageDescription"
        docs = {"README.md": "This project requires Swift 5.7"}
        result = find_swift_drift(pkg, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "5.7"
        assert result[0]["package_version"] == "5.9"

    def test_drift_minor(self):
        pkg = "// swift-tools-version:5.9\nimport PackageDescription"
        docs = {"README.md": "Swift 5.8 required"}
        result = find_swift_drift(pkg, docs)
        assert len(result) == 1

    def test_empty_package(self):
        assert find_swift_drift("", {"README.md": "Swift 5.9"}) == []

    def test_no_swift_in_docs(self):
        pkg = "// swift-tools-version:5.9\nimport PackageDescription"
        docs = {"README.md": "No version mentioned"}
        assert find_swift_drift(pkg, docs) == []

    def test_patch_difference_ignored(self):
        pkg = "// swift-tools-version:5.9.0\nimport PackageDescription"
        docs = {"README.md": "Swift 5.9.2"}
        # Major.minor comparison: 5.9 matches 5.9, patch ignored
        assert find_swift_drift(pkg, docs) == []

    def test_multiple_files(self):
        pkg = "// swift-tools-version:5.9\nimport PackageDescription"
        docs = {
            "README.md": "Swift 5.7",
            "CONTRIBUTING.md": "Swift 5.8",
        }
        result = find_swift_drift(pkg, docs)
        assert len(result) == 2


class TestSwiftIntegration:
    def test_swift_drift(self, tmp_path):
        from driftcheck.detector import scan_repo
        pkg_dir = tmp_path
        (pkg_dir / "Package.swift").write_text("// swift-tools-version:5.9\nimport PackageDescription\n")
        (pkg_dir / "README.md").write_text("# Test\n\nRequires Swift 5.7\n")
        result = scan_repo(pkg_dir)
        assert len(result["swift_drifts"]) == 1

    def test_swift_no_drift(self, tmp_path):
        from driftcheck.detector import scan_repo
        pkg_dir = tmp_path
        (pkg_dir / "Package.swift").write_text("// swift-tools-version:5.9\nimport PackageDescription\n")
        (pkg_dir / "README.md").write_text("# Test\n\nRequires Swift 5.9\n")
        result = scan_repo(pkg_dir)
        assert len(result["swift_drifts"]) == 0

    def test_no_package_swift(self, tmp_path):
        from driftcheck.detector import scan_repo
        pkg_dir = tmp_path
        (pkg_dir / "README.md").write_text("# Test\n")
        result = scan_repo(pkg_dir)
        assert len(result["swift_drifts"]) == 0
