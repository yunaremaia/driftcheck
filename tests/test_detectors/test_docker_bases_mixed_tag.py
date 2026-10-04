"""A Dockerfile mixing a pinned and an untagged base image must not crash.

`find_dockerfile_bases_drift` compares sibling Dockerfiles per image and sorts
the tag set it collected. An untagged `FROM node` parses with ``tag is None``
(``parse_dockerfile_bases`` calls that "floating"), so a repo with

    FROM node:18-alpine
    FROM node

puts ``None`` and ``"18-alpine"`` in the same set, and ``sorted`` raises
``TypeError: '<' not supported between instances of 'NoneType' and 'str'``.

The blast radius is the whole scan, not this detector. `scan_repo` calls it
un-guarded, so the exception propagates out of the CLI: exit 1, empty stdout,
no JSON, no SARIF, no CSV. Every other detector's findings in the repository
are discarded along with it, and the operator sees a traceback instead of a
report. The owner-visible symptom is a crash that looks like driftcheck is
broken, with zero evidence of the findings it had already computed.

This is the "one bad finding takes the document" shape the SARIF layer is
guarded against, arriving from the detector side instead.
"""
import json
import subprocess
import sys

from driftcheck.detectors.docker_bases import find_dockerfile_bases_drift

# A pinned stage and an untagged one for the same image.
MIXED = {"Dockerfile": "FROM node:18-alpine\nRUN a\nFROM node\nRUN b\n"}
# The same image untagged in two files: only None in the set, so sorted() is safe.
ALL_UNTAGGED = {
    "Dockerfile": "FROM node\nRUN a\n",
    "Dockerfile.ci": "FROM node\nRUN b\n",
}


def _details(result):
    return [r.get("detail", "") for r in result]


def test_mixed_pinned_and_untagged_does_not_raise():
    result = find_dockerfile_bases_drift(MIXED, {})
    assert isinstance(result, list)


def test_mixed_case_still_reports_the_floating_stage():
    """The crash must not be "fixed" by dropping the finding it interrupted.

    `FROM node` on line 3 is itself drift -- an implicit `:latest` -- and mode 1
    reports it as ``implicit latest`` rather than ``floating tag``, which is why
    this asserts on the shape (a mode-1 entry for that stage) and not on a
    guessed keyword. A fix that skips the sibling comparison must still emit the
    mode-1 finding, or it trades a crash for a false negative.
    """
    result = find_dockerfile_bases_drift(MIXED, {})
    mode_one = [r for r in result if "uses" in r.get("detail", "")]
    assert len(mode_one) == 1
    assert mode_one[0]["image"] == "node"
    assert mode_one[0]["tag"] == "(none)"
    assert mode_one[0]["line"] == 3


def test_sibling_comparison_still_reports_pinned_divergence():
    """Pinning one file and leaving the other untagged is divergence too."""
    result = find_dockerfile_bases_drift(MIXED, {})
    assert any("pinned differently" in d for d in _details(result))


def test_untagged_sibling_still_compares():
    """Two untagged siblings produce a set of one None; no divergence."""
    result = find_dockerfile_bases_drift(ALL_UNTAGGED, {})
    assert not any("pinned differently" in d for d in _details(result))


def test_no_raw_none_in_reported_tags():
    """`tags` reaches the SARIF message via `', '.join(...)`, so a None there
    would raise inside the document build and lose every finding."""
    result = find_dockerfile_bases_drift(MIXED, {})
    for entry in result:
        for tag in entry.get("tags", []):
            assert isinstance(tag, str), entry


def test_cli_reports_instead_of_crashing(tmp_path):
    """The end-to-end contract: findings survive, exit code is 1, output parses.

    A traceback would satisfy `returncode != 0` while proving nothing, so the
    assertion is on the report reaching stdout.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Dockerfile").write_text(MIXED["Dockerfile"], encoding="utf-8")
    (repo / "README.md").write_text(
        "# Doc\n\n- Node.js 14.0.0 (see package.json)\n", encoding="utf-8"
    )
    (repo / "package.json").write_text(
        json.dumps({"name": "r", "engines": {"node": ">=18.0.0"}}), encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", str(repo), "--json"],
        capture_output=True,
        text=True,
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 1, proc.stderr
    doc = json.loads(proc.stdout)
    assert doc["docker_bases_drifts"], "the floating-tag finding was lost"


def test_cli_sarif_still_builds(tmp_path):
    """The SARIF document must exist; this is the path that loses everything."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Dockerfile").write_text(MIXED["Dockerfile"], encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", str(repo), "--sarif"],
        capture_output=True,
        text=True,
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    doc = json.loads(proc.stdout)
    assert len(doc["runs"][0]["results"]) >= 1