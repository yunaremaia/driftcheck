"""Severity is one fact: what is non-blocking to the exit code is non-blocking in SARIF.

Issue #471. ``cli.INFORMATIONAL_DRIFTS`` and ``sarif.INFORMATIONAL_TYPES`` were
two independent literals that disagreed. The CLI listed six informational keys
and SARIF listed four, so ``typosquat_drifts`` and ``changelog_drifts`` exited
``0`` and printed ``info:`` while the same run published them at
``level="error"``. GitHub Code Scanning opens a **blocking** alert for an
``error``-level result, so the one finding that is simultaneously "must not
block on" and "fails your build" was a security finding: a suspected typosquat.

The registries now alias ``config.INFORMATIONAL_DRIFT_KEYS``, and
``tests/test_exit_code_gate_coverage.test_sarif_severity_matches_cli_severity``
guards that aliasing. That guard alone is not enough, and this file exists to
close the gap it leaves:

* The alias test asserts the two names are the *same object*. It says nothing
  about what ``to_sarif`` does with a key that is in it. A refactor that keeps
  the alias intact and inverts the mapping -- ``level = "error" if
  is_informational else "warning"`` -- sails past every existing test while
  turning every informational finding into a blocking Code Scanning alert. The
  defect the alias was introduced to prevent would be back, and green.
* No test asserted that a curated rule declares a severity at all. ``_make_rule``
  emitted no ``defaultConfiguration``, so the level lived only on the result.
  ``level`` on a result is what Code Scanning reads for the alert, but a rule
  with no ``defaultConfiguration`` gives every other SARIF consumer -- the
  ``filter-sarif`` family, editor integrations, anything matching on rule
  metadata -- nothing to match on, and leaves the severity unstated in the one
  place the format provides for stating it.

So the contract is pinned here against the *emitted document*, walking the
registry rather than a hand-copied list. A key added to one registry and not
the other fails; a key that stops being informational fails; a mapping
inversion fails.

Severity vocabulary is SARIF 2.1.0's: ``error`` / ``warning`` / ``note`` /
``none``. GitHub treats ``error`` as a blocking alert -- the one level that
fails the code-scanning check and, under branch protection, the merge --
while ``warning``, ``note`` and ``none`` do not block. ``error`` is therefore
the only level an informational finding may never carry, and it is the level a
blocking finding must carry.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from driftcheck import cli, sarif
from driftcheck.config import DRIFT_KEYS, INFORMATIONAL_DRIFT_KEYS
from driftcheck.sarif import DRIFT_RULES, to_sarif

# SARIF 2.1.0 `result.level`. `error` is the only level GitHub Code Scanning
# treats as blocking, so it is the only level forbidden to an informational key.
SARIF_LEVELS = {"error", "warning", "note", "none"}
BLOCKING_LEVELS = {"error"}

# A finding entry rich enough that no detector-specific formatter needs to guess:
# one `file`, one `detail`. Every key in INFORMATIONAL_DRIFT_KEYS must survive
# `_drift_message` on these fields alone, otherwise the level assertions below
# would be asserting on a result the document never emitted. That every curated
# key survives it is asserted directly in
# ``tests/test_sarif_message_retention.test_curated_keys_survive_a_generic_payload``;
# ``docker_bases_drifts`` used to need an override here to dodge a ``KeyError``
# from an unguarded ``d["image"]``, which is why no per-key payload lives in
# this file any more.
SAMPLE_FINDING = {"file": "README.md", "detail": "sample finding"}


def _levels_for(key: str) -> list[str]:
    """Every SARIF level ``key``'s sample findings are published at."""
    doc = to_sarif({key: [SAMPLE_FINDING]}, version="0.0.0")
    return [r["level"] for r in doc["runs"][0]["results"]]


def _rule_for(key: str) -> dict:
    """The rule descriptor ``key`` contributes to the driver."""
    doc = to_sarif({key: [SAMPLE_FINDING]}, version="0.0.0")
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1, f"{key} contributed {len(rules)} rules, expected 1"
    return rules[0]


def test_informational_registry_is_not_empty() -> None:
    """Guard against the extraction silently finding nothing.

    Without this, a rename of ``INFORMATIONAL_DRIFT_KEYS`` would turn every
    walk below into a vacuous pass over an empty set -- the failure mode this
    whole file exists to prevent, reproduced by accident.
    """
    assert len(INFORMATIONAL_DRIFT_KEYS) >= 7, (
        f"expected the full informational registry, got "
        f"{sorted(INFORMATIONAL_DRIFT_KEYS)}"
    )
    # The two keys #471 was filed about must stay in it.
    assert {"typosquat_drifts", "changelog_drifts"} <= INFORMATIONAL_DRIFT_KEYS, (
        "typosquat_drifts and changelog_drifts are informational to the exit "
        "code and must stay that way for the two outputs to agree"
    )


@pytest.mark.parametrize("key", sorted(INFORMATIONAL_DRIFT_KEYS))
def test_informational_key_publishes_non_blocking_level(key: str) -> None:
    """Every informational key must never reach SARIF at a blocking level."""
    levels = _levels_for(key)
    assert levels, f"{key} produced no SARIF result at all, so this is vacuous"
    blocking = sorted({lv for lv in levels} & BLOCKING_LEVELS)
    assert not blocking, (
        f"{key} is informational to the exit code (exits 0, printed as "
        f"info:) but SARIF publishes it at level={blocking}, which GitHub Code "
        f"Scanning treats as a blocking alert. The same finding must not both "
        f"be exempt from and fail the build."
    )
    unknown = sorted(set(levels) - SARIF_LEVELS)
    assert not unknown, f"{key} emitted a level outside SARIF 2.1.0: {unknown}"


@pytest.mark.parametrize("key", sorted(INFORMATIONAL_DRIFT_KEYS))
def test_informational_rule_declares_its_level(key: str) -> None:
    """The rule must state its severity, not leave it to the result.

    ``level`` on a result is what Code Scanning reads, so a missing
    ``defaultConfiguration`` is not what blocked anyone today. It is what makes
    the severity invisible to every consumer that matches on rule metadata --
    ``filter-sarif``'s ``level:`` matcher being the one that ships today --
    and it is the only place the SARIF format provides for stating a default.
    ``symlink-skipped`` already does this at sarif.py, so the mechanism is
    understood; the curated rules were simply left out of it.
    """
    rule = _rule_for(key)
    assert "defaultConfiguration" in rule, (
        f"{key}'s rule ({rule['id']}) declares no defaultConfiguration, so its "
        f"severity is unstated in the rule metadata"
    )
    declared = rule["defaultConfiguration"].get("level")
    assert declared in SARIF_LEVELS, (
        f"{key}'s rule declares level={declared!r}, outside SARIF 2.1.0"
    )
    assert declared not in BLOCKING_LEVELS, (
        f"{key}'s rule declares level={declared!r}; an informational key must "
        f"not declare a blocking default severity"
    )
    # Stated, and not stated wrongly: the rule default and the result level
    # are two spellings of one fact and must not disagree.
    assert declared == _levels_for(key)[0], (
        f"{key}'s rule declares {declared!r} but its results publish "
        f"{_levels_for(key)[0]!r}"
    )


@pytest.mark.parametrize("key", sorted(INFORMATIONAL_DRIFT_KEYS))
def test_typosquat_class_never_publishes_at_error(key: str) -> None:
    """The #471 pair specifically: typosquat and changelog are security-facing.

    A suspected typosquat is the finding a user is most likely to be relying
    on the alert for, and the one where a blocking alert is least defensible
    while the CLI still exits 0. Named explicitly so the regression names the
    issue it came from instead of reading as one more parametrised row.
    """
    if key not in {"typosquat_drifts", "changelog_drifts"}:
        pytest.skip(f"{key} is not one of the two keys #471 was filed about")
    assert all(lv != "error" for lv in _levels_for(key)), (
        f"{key} is published at level=error; a security-facing finding that "
        f"exits 0 must not open a blocking Code Scanning alert"
    )


def test_the_two_registries_cannot_drift_apart() -> None:
    """Walk both names and require agreement -- the anti-drift guard.

    Both are aliases of one set today, so this asserts what the alias already
    guarantees. Its value is the failure it makes loud: reintroduce a second
    literal in either module and this reports the exact disagreement instead of
    letting a future key land in one registry and not the other. Equal-but-
    separate copies are the shape this bug had, and they are what made it
    possible for two keys to diverge while every test stayed green.
    """
    cli_set = set(cli.INFORMATIONAL_DRIFTS)
    sarif_set = set(sarif.INFORMATIONAL_TYPES)
    only_cli = sorted(cli_set - sarif_set)
    only_sarif = sorted(sarif_set - cli_set)
    assert not only_cli and not only_sarif, (
        f"severity registries disagree -- informational to the exit code only: "
        f"{only_cli} (published at level=error, so a blocking alert for a "
        f"finding that exits 0); informational in SARIF only: {only_sarif} "
        f"(never blocks in Code Scanning but fails the build)"
    )
    assert cli_set == sarif_set == set(INFORMATIONAL_DRIFT_KEYS), (
        "both registries must resolve to config.INFORMATIONAL_DRIFT_KEYS"
    )


def test_informational_keys_are_registered_drift_keys() -> None:
    """An informational key outside ``DRIFT_KEYS`` gates nothing and routes nothing."""
    unknown = sorted(INFORMATIONAL_DRIFT_KEYS - set(DRIFT_KEYS))
    assert not unknown, f"informational keys absent from DRIFT_KEYS: {unknown}"


@pytest.mark.parametrize("key", sorted(set(DRIFT_KEYS) - INFORMATIONAL_DRIFT_KEYS))
def test_blocking_key_still_publishes_at_error(key: str) -> None:
    """The positive control: the fix must not demote blocking findings.

    A change that made everything ``warning`` would satisfy every test above.
    This is what rules that out: a key outside the informational registry has
    to keep failing the build *and* keep raising a blocking Code Scanning
    alert, because that is the whole point of a blocking finding.
    """
    levels = _levels_for(key)
    assert levels, f"{key} produced no SARIF result, so this is vacuous"
    assert all(lv == "error" for lv in levels), (
        f"{key} is blocking to the exit code but SARIF publishes it at "
        f"{sorted(set(levels))}; demoting a blocking finding to a "
        f"non-blocking level silences it in Code Scanning while it still fails "
        f"the build"
    )
    assert _rule_for(key)["defaultConfiguration"]["level"] == "error", (
        f"{key} is blocking but its rule does not declare level=error"
    )


def test_sarif_document_is_valid_json_with_levels_in_vocabulary() -> None:
    """Serialize the real document and re-read it.

    Everything above inspects the Python dict. This proves the bytes the action
    uploads to Code Scanning carry the same levels, so a level cannot be
    dropped by anything between ``to_sarif`` and ``json.dumps``.
    """
    result = {
        "typosquat_drifts": [
            {"file": "requirements.txt", "detail": "suspicious dependency 'reqeusts'"}
        ],
        "lockfile_drifts": [
            {"file": "requirements.txt", "detail": "missing requirements.txt.lock"}
        ],
        "rust_drifts": [
            {"file": "README.md", "doc_version": "1.80.0", "toolchain_version": "1.85.0"}
        ],
    }
    doc = json.loads(json.dumps(to_sarif(result, version="0.0.0")))
    by_rule = {r["ruleId"]: r["level"] for r in doc["runs"][0]["results"]}
    assert by_rule == {
        "typosquat-suspect": "warning",
        "lockfile-drift": "warning",
        "rust-cargo-version-drift": "error",
    }, f"severity levels changed in the serialized document: {by_rule}"


def test_end_to_end_typosquat_exits_zero_and_publishes_warning() -> None:
    """The full reproduction from #471, against the real CLI.

    Asserts both halves of the contract at once, because the bug was a
    disagreement between them: a typosquat must exit 0 *and* publish at a
    non-blocking level. Asserting the level alone would pass on a tree where
    typosquat had been promoted to blocking; asserting the exit code alone
    would pass on today's tree, which is the defect #471 was filed about.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # edit distance 2 from 'requests'
        (root / "requirements.txt").write_text("reqeusts==2.31.0\n", encoding="utf-8")
        (root / "README.md").write_text("# P\n", encoding="utf-8")
        (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")

        text = subprocess.run(
            [sys.executable, "-m", "driftcheck", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert text.returncode == 0, (
            f"text mode exited {text.returncode} on a typosquat-only fixture: "
            f"{text.stdout[-400:]}"
        )
        assert "typosquat" in text.stdout.lower(), (
            f"expected the typosquat in the text report: {text.stdout[-400:]}"
        )

        sarif_run = subprocess.run(
            [sys.executable, "-m", "driftcheck", str(root), "--sarif"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        doc = json.loads(sarif_run.stdout)
        levels = {
            r["ruleId"]: r["level"] for r in doc["runs"][0]["results"]
        }
        assert "typosquat-suspect" in levels, (
            f"the typosquat finding is missing from --sarif entirely: {levels}"
        )
        assert levels["typosquat-suspect"] != "error", (
            f"typosquat-suspect is published at level=error while the same run "
            f"exits 0 -- this is issue #471: {levels}"
        )


def test_rule_ids_stay_unique_so_one_default_per_rule_is_sound() -> None:
    """``defaultConfiguration`` is per rule; shared ids would make it a lie.

    Two drift keys mapped to one rule id would leave a single default level
    describing results that disagree, and the per-key assertions above would
    pass while the document contradicts itself.
    """
    seen: dict[str, list[str]] = {}
    for key, (rule_id, _name, _desc) in DRIFT_RULES.items():
        seen.setdefault(rule_id, []).append(key)
    shared = {rid: keys for rid, keys in seen.items() if len(keys) > 1}
    assert not shared, f"rule ids shared by several drift keys: {shared}"