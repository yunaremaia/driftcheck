"""The shared fallback pairs a documented value with the value it should carry.

``_print_report`` assembled its mismatch sentence from a hand-written list of
six ``*_version`` field names, so the 32 other version-ish fields the other
surfaces look up were unreachable and the sentence rendered with an empty
target. These tests pin the replacement: the expected value is found by
knowing what the *documented* side looks like, not by enumerating what the
toolchain side might call itself.
"""

from __future__ import annotations

from driftcheck.messages import describe_drift, describe_expected, describe_finding


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
    payload = {"file": "README.md", "tool": "python", "doc_version": "3.9",
               "version_file": "3.12"}
    assert describe_expected(payload) == "3.12"
    assert describe_drift(payload) == "Python 3.9 → should be 3.12"


def test_a_field_nobody_predicted_is_still_paired() -> None:
    """An unforeseen field name is described, not dropped.

    This is the structural guarantee: the payload carries the value, so the
    renderer reads it rather than deciding up front which keys exist.
    """
    payload = {"file": "Chart.yaml", "chart": "api", "vault_image": "ghcr.io/vault:1.2"}
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