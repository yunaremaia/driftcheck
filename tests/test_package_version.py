"""Tests for package.json version drift detection."""
from driftcheck.detector import scan_repo
from driftcheck.detectors.fix import apply_fixes
from driftcheck.detectors.package_version import (
    find_package_version_drift,
    fix_package_version_reference,
    parse_package_identity,
)


def test_parse_package_identity():
    assert parse_package_identity('{"name":"demo","version":"1.2.3"}') == (
        "demo",
        "1.2.3",
    )


def test_matching_version_has_no_drift():
    package = '{"name":"demo","version":"1.2.3"}'
    docs = {"README.md": "npm install demo@1.2.3"}
    assert find_package_version_drift(package, docs) == []


def test_install_command_drift():
    package = '{"name":"demo","version":"1.2.3"}'
    drifts = find_package_version_drift(
        package, {"README.md": "Run npm install demo@1.2.0"}
    )
    assert len(drifts) == 1
    assert drifts[0]["kind"] == "install"
    assert drifts[0]["doc_version"] == "1.2.0"
    assert drifts[0]["package_version"] == "1.2.3"


def test_badge_url_drift():
    package = '{"name":"demo","version":"2.0.0"}'
    drifts = find_package_version_drift(
        package,
        {"README.md": "https://img.shields.io/npm/v/demo/1.9.0"},
    )
    assert len(drifts) == 1
    assert drifts[0]["kind"] == "badge"


def test_changelog_header_drift():
    package = '{"name":"demo","version":"3.0.0"}'
    drifts = find_package_version_drift(
        package, {"README.md": "## [2.9.0]\nChanges here"}
    )
    assert len(drifts) == 1
    assert drifts[0]["kind"] == "changelog"


def test_missing_package_version_is_ignored():
    assert find_package_version_drift(
        '{"name":"demo"}', {"README.md": "npm install demo@1.0.0"}
    ) == []


def test_multiple_mismatches_are_reported():
    package = '{"name":"demo","version":"2.0.0"}'
    docs = {
        "README.md": (
            "https://img.shields.io/npm/v/demo/1.0.0\n"
            "npm install demo@1.5.0\n"
        )
    }
    drifts = find_package_version_drift(package, docs)
    assert {d["kind"] for d in drifts} == {"badge", "install"}


def test_fix_package_version_reference():
    drift = {
        "kind": "install",
        "package": "demo",
        "doc_version": "1.2.0",
        "package_version": "1.2.3",
    }
    assert (
        fix_package_version_reference("npm install demo@1.2.0", drift)
        == "npm install demo@1.2.3"
    )


def test_scan_repo_registers_package_version_drift(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name":"demo","version":"2.0.0"}'
    )
    (tmp_path / "README.md").write_text(
        "Install with npm install demo@1.0.0\n"
    )
    result = scan_repo(tmp_path)
    assert result["package_version_drifts"]
    assert result["package_version_drifts"][0]["package_version"] == "2.0.0"


def test_apply_fixes_updates_package_reference(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("npm install demo@1.0.0\n")
    result = {
        "package_version_drifts": [
            {
                "file": "README.md",
                "kind": "install",
                "package": "demo",
                "doc_version": "1.0.0",
                "package_version": "2.0.0",
            }
        ]
    }
    assert apply_fixes(tmp_path, result) == ["README.md"]
    assert "demo@2.0.0" in readme.read_text()
