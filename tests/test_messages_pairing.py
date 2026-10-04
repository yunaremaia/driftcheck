"""The shared fallback pairs a documented value with the value it should carry.

``_print_report`` assembled its mismatch sentence from a hand-written list of
six ``*_version`` field names, so the 32 other version-ish fields the other
surfaces look up were unreachable and the sentence rendered with an empty
target. These tests pin the replacement: the expected value is found by
knowing what the *documented* side looks like, not by enumerating what the
toolchain side might call itself.
"""

from __future__ import annotations

from driftcheck.messages import (
    describe_drift,
    describe_expected,
    describe_finding,
    describe_pair,
)


def test_detector_detail_is_preserved_verbatim() -> None:
    """A detector that wrote a sentence keeps it, unrewritten."""
    payload = {"file": "go.mod", "detail": "errors v0.9.1 missing from go.sum"}
    assert describe_drift(payload) == "errors v0.9.1 missing from go.sum"


def test_documented_and_actual_values_are_paired_generically() -> None:
    """The expected value is found by subtraction, not from a name list.

    ``version_file`` is one of the 32 fields the old six-name list could not
    reach. Finding it requires knowing only what the *documented* side looks
    like, so a detector's novel field name is picked up without a line here.
    """
    payload = {"file": "README.md", "tool": "Python", "doc_version": "3.9",
               "version_file": "3.12"}
    assert describe_expected(payload) == "3.12"
    assert describe_drift(payload) == "Python 3.9 → should be 3.12"


def test_a_field_nobody_predicted_is_still_paired() -> None:
    """An unforeseen field name is described, not dropped.

    This is the structural guarantee: the payload carries the value, so the
    renderer reads it rather than deciding up front which keys exist. The
    documented side is present, because without one there is no mismatch to
    state -- ``test_payload_with_nothing_to_pair_falls_back_to_the_summary``
    pins that half.
    """
    payload = {"file": "Chart.yaml", "chart": "api", "doc_image": "vault:1.1",
               "vault_image": "ghcr.io/vault:1.2"}
    assert describe_expected(payload) == "ghcr.io/vault:1.2"


def test_payload_with_nothing_to_pair_falls_back_to_the_summary() -> None:
    """No documented side means no mismatch sentence to invent."""
    payload = {"file": "README.md", "rule": "probe-rule", "expected": "2.0", "pos": 0}
    assert describe_expected(payload) == ""
    assert describe_drift(payload) == "rule=probe-rule expected=2.0"
    assert describe_drift(payload) == describe_finding(payload)


def test_only_the_documented_side_present_yields_no_sentence() -> None:
    """Half a mismatch is not a mismatch; describe the payload instead.

    Emitting "X should be" with nothing after it is the failure mode, so a
    payload carrying only the documented side must not take that path.
    """
    payload = {"file": "README.md", "tool": "python", "doc_version": "3.9"}
    assert describe_expected(payload) == ""
    assert "should be" not in describe_drift(payload)
    assert describe_drift(payload) == "tool=python doc_version=3.9"


def test_non_dict_payload_still_produces_text() -> None:
    """A non-dict entry is described rather than raising."""
    assert describe_drift("plain string finding") == "plain string finding"
    assert describe_expected("plain string finding") == ""


def test_a_label_before_the_documented_side_is_not_the_target() -> None:
    """A name that describes the finding is never the value it wants.

    Real payloads, not invented ones. ``package_version_drifts`` emits
    ``package`` and ``python_version_drifts`` emits ``type``, both *before* the
    documented value, so a subtraction that scanned from the top of the payload
    returned the package name or the word "doc" as the version the docs should
    carry -- "left-pad 1.0.0 -> should be left-pad", which reads as a
    rendering bug in a sentence built to prevent exactly that.

    The counterpart follows the documented side, so the scan starts there.
    """
    package = {"file": "CHANGELOG.md", "kind": "changelog", "package": "left-pad",
               "doc_version": "1.0.0", "package_version": "2.0.0", "pos": 17}
    assert describe_expected(package) == "2.0.0"

    python = {"file": "README.md", "type": "doc", "tool": "Python",
              "doc_version": "3.9", "version_file": "3.11.0",
              "floor_version": "3.11.0", "floor_source": "pyproject.toml", "pos": 0}
    assert describe_expected(python) == "3.11.0"
    assert describe_drift(python) == "Python 3.9 → should be 3.11.0"

# --- describe_pair: both halves, for payloads that name no documented side ---
#
# Every payload below is verbatim from `--json` output of a real scan (see the
# counts in each docstring), not a shape invented for the test. The pairing rule
# is load-bearing for `--explain`, which renders Actual/Expected/Diff/Fix, so
# these pin what it must never do as much as what it must do.


def test_documented_field_payload_pairs_that_field_with_the_counterpart() -> None:
    """A payload naming its documented side still pairs the documented field.

    Real ``git_tag_drifts`` payload: ``detail`` describes the drift, and the two
    values it disagrees about are ``doc_version`` and ``git_tag`` -- a field
    name the closed subtraction set does not have to know.
    """
    payload = {"file": "README.md", "doc_version": "1.0", "git_tag": "v0.1.0",
               "detail": "README mentions version 1.0 but latest git tag is v0.1.0",
               "pos": 198}
    assert describe_pair(payload) == ("1.0", "v0.1.0")


def test_pair_is_read_from_payloads_that_name_no_documented_side() -> None:
    """The majority case: no ``doc_*`` field, and both halves are still reachable.

    Real ``actions_drifts`` payload from ``a2a-drift/.github/workflows/ci.yml``.
    Measured over 330 findings across 35 repos, 301 carry no documented field --
    these are the findings ``--explain`` used to render with an empty ``Actual``,
    an empty ``Expected`` and no diff, while the same finding printed correctly
    in the scan.
    """
    payload = {"file": ".github/workflows/ci.yml", "action": "actions/checkout",
               "current": "v4", "suggested": "v5", "pos": 556}
    assert describe_pair(payload) == ("v4", "v5")


def test_a_subject_label_is_never_rendered_as_one_of_the_two_values() -> None:
    """A payload that names its subject leads with it; the values follow.

    Real ``freshness_drifts`` payload: ``package`` is what the versions are
    *about*, not either side of the mismatch. This is the shape the trailing-two
    rule exists for -- measured over the real corpus, no ``action``, ``package``,
    ``instruction`` or ``type`` value appeared in a returned pair.
    """
    payload = {"file": "pyproject.toml", "package": "httpx", "pinned_version": "0.27",
               "latest_version": "0.28.1", "pos": 0}
    assert describe_pair(payload) == ("0.27", "0.28.1")


def test_the_detectors_own_sentence_is_never_one_half_of_the_pair() -> None:
    """``detail`` and ``message`` describe the finding, so they cannot be a value.

    Real ``uv_lock_drifts`` payload from ``tool-call-retry/uv.lock``. Its
    ``message`` restates both versions in a sentence ("pyyaml: uv.lock=6.0.3,
    pyproject.toml=>=6.0"); pairing against it would print the sentence as one
    side of a diff.
    """
    payload = {"type": "uv_lock_drift", "package": "pyyaml", "uv_lock_version": "6.0.3",
               "pyproject_spec": ">=6.0", "file": "uv.lock",
               "message": "pyyaml: uv.lock=6.0.3, pyproject.toml=>=6.0"}
    assert describe_pair(payload) == ("6.0.3", ">=6.0")


def test_an_instruction_label_is_not_read_as_the_documented_value() -> None:
    """A payload whose subject is named by an invented field is still read.

    Real ``dockerfile_instruction_drifts`` payload from
    ``gfi/CONTRIBUTING.md``. Its documented side is ``doc_value`` -- outside the
    ``_DOCUMENTED_FIELDS`` vocabulary, so the documented branch does not apply and
    the subtraction carries this finding. ``instruction`` names what is being
    documented and must not become the value.
    """
    payload = {"file": "CONTRIBUTING.md", "instruction": "ENTRYPOINT",
               "doc_value": "is", "dockerfile_value": '["gfi"]', "pos": 2720}
    assert describe_pair(payload) == ("is", '["gfi"]')


def test_a_finding_naming_a_condition_rather_than_two_values_has_no_pair() -> None:
    """``kind`` + ``detail`` is a condition, not a disagreement.

    Real ``typosquat_drifts`` payload: a suspicious package is reported with a
    condition and a sentence, and there is nothing to diff. Returning None is
    what lets the caller render the detector's own sentence instead of inventing
    a missing half -- 87 of the 301 real payloads with no documented field are
    of this shape.
    """
    payload = {"file": "pyproject.toml", "kind": "typosquat_suspect",
               "detail": "suspicious dependency 'pretty' \u2014 edit distance <= 2 "
                         "from known package(s): poetry (possible typosquat)",
               "pos": 0}
    assert describe_pair(payload) is None




def test_non_dict_payload_has_no_pair() -> None:
    """A non-dict entry has no fields to read, so it has no pair."""
    assert describe_pair("plain string finding") is None
    assert describe_pair(42) is None
    assert describe_pair(None) is None


def test_a_list_valued_field_is_not_one_half_of_the_pair() -> None:
    """Two values are not two versions.

    Real ``dependabot_incomplete`` payload from ``agent-undo``. Both surviving
    fields hold *lists* of ecosystem names, so the trailing-two rule pairs
    ``("['github-actions']", "['pip']")`` -- a Python repr rendered as a version
    on each side of a diff, and a substitution nobody can apply to YAML. This is
    the one measured payload where trailing-two names a pair that is not a pair:
    3 of the 214 real no-documented-field payloads that reach it. A value a
    reader would compare is a scalar; a collection is part of the condition, and
    ``describe_finding`` already renders it well.
    """
    payload = {"file": ".github/dependabot.yml", "kind": "dependabot_incomplete",
               "ecosystems": ["github-actions", "pip"], "configured": ["npm"],
               "detail": "dependabot.yml missing ecosystems: github-actions"}
    assert describe_pair(payload) is None
