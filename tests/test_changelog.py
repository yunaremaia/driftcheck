"""Tests for changelog entry drift detection."""
import tempfile
from pathlib import Path

from driftcheck.detectors.changelog import (
    _changelog_policy_required,
    _changelog_has_content,
    _changelog_has_version_sections,
    _changelog_has_recent_activity,
    _changelog_has_unreleased_section,
    find_changelog_drift,
)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestChangelogPolicyRequired:
    def test_explicit_require(self):
        text = "All PRs must include a CHANGELOG entry."
        assert _changelog_policy_required(text, "") is True

    def test_per_pr_mention(self):
        text = "Per PR, please update the changelog."
        assert _changelog_policy_required(text, "") is True

    def test_missing_forgotten(self):
        text = "We noticed the CHANGELOG was not updated in several PRs."
        assert _changelog_policy_required(text, "") is True

    def test_implicit_document_changes(self):
        text = "Document all changes in the changelog."
        assert _changelog_policy_required(text, "") is True

    def test_no_policy(self):
        text = "Please lint your code."
        assert _changelog_policy_required(text, "") is False

    def test_empty(self):
        assert _changelog_policy_required("", "") is False

    def test_policy_ignored_when_changelog_present_and_populated(self):
        # When the file exists with content, the helper still returns True,
        # but the detector will not fire a missing/empty drift.
        text = "Every PR must update the CHANGELOG."
        changelog = "# Changelog\n\n## [1.0.0] - 2026-01-01\n- Initial release"
        assert _changelog_policy_required(text, changelog) is True


class TestChangelogHasContent:
    def test_empty(self):
        assert _changelog_has_content("") is False

    def test_whitespace_only(self):
        assert _changelog_has_content("   \n\t  ") is False

    def test_populated(self):
        assert _changelog_has_content("# Changelog\n\nSome text") is True


class TestChangelogHasVersionSections:
    def test_no_headers(self):
        assert _changelog_has_version_sections("Just some text") is False

    def test_release_header(self):
        text = "## [1.2.3] - 2026-09-01\n- Fixed stuff"
        assert _changelog_has_version_sections(text) is True

    def test_unreleased_only(self):
        # Unreleased is not a release header
        text = "## [Unreleased]\n- WIP"
        assert _changelog_has_version_sections(text) is False

    def test_multiple_releases(self):
        text = "## [1.0.0] - 2025-01-01\n\n## [2.0.0] - 2026-01-01\n"
        assert _changelog_has_version_sections(text) is True


class TestChangelogHasUnreleasedSection:
    def test_present(self):
        text = "## [Unreleased]\n- Added X"
        assert _changelog_has_unreleased_section(text) is True

    def test_absent(self):
        text = "## [1.0.0] - 2026-01-01\n- Initial"
        assert _changelog_has_unreleased_section(text) is False


class TestChangelogHasRecentActivity:
    def test_unreleased(self):
        text = "## [Unreleased]\n- Added X"
        assert _changelog_has_recent_activity(text) is True

    def test_release_header_present(self):
        text = "## [1.2.3] - 2026-09-01\n- Fixed stuff"
        assert _changelog_has_recent_activity(text) is True

    def test_no_release_headers(self):
        text = "Just notes, no version headers"
        assert _changelog_has_recent_activity(text) is False


# ---------------------------------------------------------------------------
# Integration-style tests via scan_repo
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        full = tmp_path / name
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return tmp_path


def test_changelog_missing_with_policy(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "All PRs must include a CHANGELOG entry.",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 1
    assert result["changelog_drifts"][0]["kind"] == "changelog_missing"


def test_changelog_empty_with_policy(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "Please update the changelog for each PR.",
        "CHANGELOG.md": "",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 1
    assert result["changelog_drifts"][0]["kind"] == "changelog_empty"


def test_changelog_no_versions_with_policy(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "Every PR must document changes.",
        "CHANGELOG.md": "# Changelog\n\nNo releases yet.",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 1
    assert result["changelog_drifts"][0]["kind"] == "changelog_no_versions"


def test_changelog_ok_with_policy(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "Please add a CHANGELOG entry per PR.",
        "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n- Initial",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 0


def test_changelog_policy_not_required_no_drift(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "Please follow the style guide.",
        "CHANGELOG.md": "",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 0


def test_changelog_no_contributing_no_drift(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "README.md": "A project",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    assert len(result["changelog_drifts"]) == 0


def test_changelog_stale_heuristic(tmp_path: Path) -> None:
    _make_repo(tmp_path, {
        "CONTRIBUTING.md": "CHANGELOG entries are required.",
        "CHANGELOG.md": "# Changelog\n\nOld notes, no version headers and no unreleased section.",
    })
    from driftcheck.detector import scan_repo
    result = scan_repo(tmp_path)
    drifts = result["changelog_drifts"]
    # Should at least fire the no_versions drift
    kinds = {d["kind"] for d in drifts}
    assert "changelog_no_versions" in kinds


def test_changelog_in_list_detectors(tmp_path: Path) -> None:
    _make_repo(tmp_path, {"README.md": "test"})
    from driftcheck.cli import main
    import io, sys
    out = io.StringIO()
    sys.stdout = out
    try:
        main(["--list-detectors"])
    finally:
        sys.stdout = sys.__stdout__
    assert "changelog" in out.getvalue()
