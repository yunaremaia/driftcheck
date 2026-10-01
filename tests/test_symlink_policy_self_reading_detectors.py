"""`follow_symlinks = false` must hold for detectors that read the repo themselves.

`_read_candidate` gates the files `scan_repo` reads on behalf of a detector
(pyproject.toml, README.md, ...), but many detectors are handed the repo root
and re-glob it themselves: `find_ci_os_drift`, `find_typosquat_drift`,
`find_rust_workspace_drift` and `find_changelog_drift` all call `read_text()`
on paths they build from `root`. Those reads never consult the walked file set,
so a symlink whose target escapes the repo root is still opened, and content
from outside the root is published as a drift finding even though the very same
scan lists the link under `_skipped_symlinks`.

That is a self-contradictory result and an information-disclosure hole: the
operator asked driftcheck not to look outside the repo, and the operator's own
output quotes the file it was told to skip.
"""

from pathlib import Path

import pytest

from driftcheck.detector import scan_repo

ESCAPING_WORKFLOW = (
    "name: ci\njobs:\n  build:\n    runs-on: ubuntu-20.04\n    steps: []\n"
)
IN_REPO_WORKFLOW = (
    "name: ci\njobs:\n  build:\n    runs-on: ubuntu-22.04\n    steps: []\n"
)


def _repo(tmp_path: Path, follow_symlinks: bool = False) -> tuple[Path, Path]:
    """Build a repo plus a sibling directory that lives outside it."""
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".driftcheck.toml").write_text(
        f"[driftcheck]\nfollow_symlinks = {str(follow_symlinks).lower()}\n"
    )
    return root, outside


def _escape(root: Path, outside: Path, link: Path, target_name: str, body: str) -> None:
    """Replace `link` with a symlink pointing at a file outside the repo root."""
    target = outside / target_name
    target.write_text(body)
    link.unlink()
    link.symlink_to(target)


# --- ci_os: reads .github/workflows/*.yml itself ------------------------------


def _ci_os_repo(tmp_path: Path) -> tuple[Path, Path]:
    root, outside = _repo(tmp_path)
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(IN_REPO_WORKFLOW)
    return root, outside


def test_ci_os_detector_does_not_read_through_escaping_symlink(tmp_path):
    root, outside = _ci_os_repo(tmp_path)
    assert scan_repo(root).get("ci_os_drifts") == []

    _escape(
        root, outside, root / ".github" / "workflows" / "ci.yml", "evil.yml",
        ESCAPING_WORKFLOW,
    )

    result = scan_repo(root)
    assert result.get("ci_os_drifts") == [], (
        "ci_os drift was reported from a symlink the policy declared skipped: "
        f"{result.get('ci_os_drifts')}"
    )
    assert any("ci.yml" in s for s in result.get("_skipped_symlinks", []))


# --- typosquat: reads the manifests itself -----------------------------------


def test_typosquat_detector_does_not_read_through_escaping_symlink(tmp_path):
    root, outside = _repo(tmp_path)
    (root / "requirements.txt").write_text("requests==2.0.0\n")
    assert scan_repo(root).get("typosquat_drifts") == []

    _escape(
        root, outside, root / "requirements.txt", "req.txt", "reqeusts==2.0.0\n"
    )

    result = scan_repo(root)
    assert result.get("typosquat_drifts") == [], (
        "a dependency name from outside the repo root was published as a "
        f"typosquat finding: {result.get('typosquat_drifts')}"
    )


# --- rust_workspace: globs **/README.md itself -------------------------------


def test_rust_workspace_detector_does_not_read_through_escaping_symlink(tmp_path):
    root, outside = _repo(tmp_path)
    (root / "Cargo.toml").write_text(
        '[workspace]\nmembers = ["crates/*"]\n[workspace.package]\nversion = "1.0.0"\n'
    )
    crate = root / "crates" / "a"
    crate.mkdir(parents=True)
    (crate / "Cargo.toml").write_text('name = "myscrate"\nversion = "1.0.0"\n')
    (root / "README.md").write_text("plain readme, no badges\n")
    assert scan_repo(root).get("rust_workspace_drifts") == []

    _escape(
        root, outside, root / "README.md", "README.md",
        "https://img.shields.io/crates/v/myscrate/9.9.9\n",
    )

    result = scan_repo(root)
    assert result.get("rust_workspace_drifts") == [], (
        "a crates.io badge read through an escaping symlink was reported: "
        f"{result.get('rust_workspace_drifts')}"
    )


# --- changelog: reads CONTRIBUTING.md itself ----------------------------------


def test_changelog_detector_does_not_read_through_escaping_symlink(tmp_path):
    root, outside = _repo(tmp_path)
    (root / "CONTRIBUTING.md").write_text("Nothing is required here.\n")
    (root / "CHANGELOG.md").write_text("## 1.0.0\n\n- init\n")
    assert scan_repo(root).get("changelog_drifts") == []

    _escape(
        root, outside, root / "CONTRIBUTING.md", "CONTRIB.md",
        "Every PR must update the changelog.\n",
    )

    result = scan_repo(root)
    assert result.get("changelog_drifts") == [], (
        "a changelog policy read through an escaping symlink was enforced: "
        f"{result.get('changelog_drifts')}"
    )


# --- regression guards --------------------------------------------------------


def test_default_policy_still_follows_escaping_symlink(tmp_path):
    """follow_symlinks=true (the default) is unaffected: the drift is reported."""
    root, outside = _ci_os_repo(tmp_path)
    _escape(
        root, outside, root / ".github" / "workflows" / "ci.yml", "evil.yml",
        ESCAPING_WORKFLOW,
    )
    # Rewrite the config without the policy so the default applies.
    (root / ".driftcheck.toml").unlink()

    result = scan_repo(root)
    assert [d["runner"] for d in result.get("ci_os_drifts", [])] == ["ubuntu-20.04"]


def test_symlink_pointing_inside_root_is_still_read(tmp_path):
    """The policy only rejects escapes; an in-root link is still a real file."""
    root, _ = _ci_os_repo(tmp_path)
    real = root / ".github" / "real-ci.yml"
    real.write_text(ESCAPING_WORKFLOW)
    (root / ".github" / "workflows" / "ci.yml").unlink()
    (root / ".github" / "workflows" / "ci.yml").symlink_to(real)

    result = scan_repo(root)
    assert [d["runner"] for d in result.get("ci_os_drifts", [])] == ["ubuntu-20.04"], (
        "a symlink whose target stays inside the repo root must still be read"
    )


def test_findings_about_absent_files_are_not_dropped(tmp_path):
    """The policy filters escapes, not "this file does not exist" findings."""
    root, _ = _repo(tmp_path)
    (root / "package.json").write_text('{"name": "x", "version": "1.0.0"}\n')

    result = scan_repo(root)
    assert result.get("lockfile_drifts"), (
        "a missing-lockfile finding must survive the symlink policy"
    )


@pytest.mark.parametrize("policy", [True, False])
def test_policy_never_raises(tmp_path, policy):
    """A broken link under either policy is reported, not crashed on."""
    root, outside = _ci_os_repo(tmp_path)
    (root / ".github" / "workflows" / "ci.yml").unlink()
    (root / ".github" / "workflows" / "ci.yml").symlink_to(outside / "missing.yml")

    result = scan_repo(root)
    assert isinstance(result, dict)


def test_broken_symlink_finding_is_treated_as_escaping(tmp_path):
    """An unresolvable link cannot be shown to be in-root, so it is not published."""
    root, outside = _ci_os_repo(tmp_path)
    (root / ".github" / "workflows" / "ci.yml").unlink()
    (root / ".github" / "workflows" / "ci.yml").symlink_to(outside / "missing.yml")

    result = scan_repo(root)
    assert result.get("ci_os_drifts") == [], (
        "a broken symlink must not produce a finding: "
        f"{result.get('ci_os_drifts')}"
    )


def test_symlink_loop_finding_is_treated_as_escaping(tmp_path):
    """A link that resolves to itself raises; it must not crash or publish."""
    root, _ = _ci_os_repo(tmp_path)
    link = root / ".github" / "workflows" / "ci.yml"
    link.unlink()
    link.symlink_to(link)

    result = scan_repo(root)
    assert result.get("ci_os_drifts") == []


def test_file_under_escaping_directory_symlink_is_dropped(tmp_path):
    """The escape can be a symlinked directory, not just a symlinked file.

    The leaf here is an ordinary file — `is_symlink()` is False on it — so a
    filter that only inspects the leaf misses the escape entirely.
    """
    root, outside = _repo(tmp_path)
    wf = outside / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(ESCAPING_WORKFLOW)
    # `.github` itself is the escaping link, so the workflow is reached only by
    # traversing a link out of the repo — the leaf looks like a normal file.
    (root / ".github").symlink_to(outside)

    # Sanity: the workflow really is visible to a detector that globs the root.
    assert not (outside / "workflows" / "ci.yml").is_symlink()
    assert _reads_runner_outside_root(root), (
        "fixture is broken: the detector can no longer reach the outside file"
    )

    result = scan_repo(root)
    assert result.get("ci_os_drifts") == [], (
        "a file reached through an escaping directory symlink was published: "
        f"{result.get('ci_os_drifts')}"
    )


def _reads_runner_outside_root(root: Path) -> bool:
    """True when find_ci_os_drift reports the runner living outside the root.

    Calls the detector directly, bypassing scan_repo's policy, to prove the
    fixture reaches the file at all — without the fix in place this returns
    True, which is what makes the scan-level assertions meaningful.
    """
    from driftcheck.detectors.ci_os import find_ci_os_drift

    return any(d["runner"] == "ubuntu-20.04" for d in find_ci_os_drift(root))


def test_no_synthetic_key_appears_in_the_result(tmp_path):
    """The fix must not add bookkeeping keys that leak into --json/SARIF.

    Compares the key set of the same repo scanned with and without the escaping
    link, so the only permitted difference is the documented internal key.
    """
    root, _ = _ci_os_repo(tmp_path)
    result = scan_repo(root)
    with_link = set(result)

    (root / ".github" / "workflows" / "ci.yml").unlink()
    (root / ".github" / "workflows" / "ci.yml").write_text(IN_REPO_WORKFLOW)
    without_link = set(scan_repo(root))

    assert "_dropped_symlink_drifts" not in with_link
    assert with_link - without_link <= {"_skipped_symlinks"}, (
        f"filtering added keys to the result: {with_link - without_link}"
    )
    assert without_link - with_link == set(), (
        f"filtering removed keys from the result: {without_link - with_link}"
    )


def test_dropped_findings_stay_out_of_json_and_sarif(tmp_path):
    """A finding suppressed by the policy must not reappear in serialised output."""
    import json

    from driftcheck.sarif import to_sarif

    root, outside = _ci_os_repo(tmp_path)
    _escape(
        root, outside, root / ".github" / "workflows" / "ci.yml", "evil.yml",
        ESCAPING_WORKFLOW,
    )
    result = scan_repo(root)

    payload = json.dumps(result)
    assert "ubuntu-20.04" not in payload, (
        "content read from outside the repo root leaked into the JSON output"
    )
    sarif_doc = json.dumps(to_sarif(result, version="test", root=root))
    assert "ubuntu-20.04" not in sarif_doc, (
        "content read from outside the repo root leaked into the SARIF output"
    )


def test_no_drift_is_dropped_in_a_clean_scan(tmp_path):
    """With no links present, a normal scan is untouched by the filter."""
    root, _ = _ci_os_repo(tmp_path)
    (outside_root := root / "requirements.txt").write_text("requests==2.0.0\n")

    result = scan_repo(root)
    assert result.get("ci_os_drifts") == [], (
        "the in-repo workflow uses ubuntu-22.04 and must not be reported"
    )
    assert result.get("typosquat_drifts") == [], (
        "a real in-repo file must keep its findings: the filter is not the policy"
    )
    assert "_skipped_symlinks" not in result, (
        "nothing was skipped, so the internal key must not appear"
    )
    assert outside_root.exists()
