"""A detector's reported line number must reach the SARIF region.

The line a detector computes is delivered work: `docker_bases` and
`docker_multistage` both count the newline offset of the ``FROM`` they matched
and carry it as ``line``, and the text printer prints it
(``cli._print_blocking_drifts`` renders ``d['file']}:{d['line']}``). SARIF
dropped it -- `_make_result` accepted a ``line`` keyword that no caller ever
passed, so every result was pinned to ``startLine: 1``.

The consequence is not cosmetic. Code Scanning renders an alert at the region
it is given, so a Dockerfile whose stages sit on lines 6, 9 and 12 produced
three results that all pointed at line 1 of the same file: indistinguishable in
the UI, and a click that lands the engineer on the wrong statement. The finding
count was correct and the alert count was correct, which is why every registry
diff in this project stayed green while the location was wrong.

The `pos` sibling matters too, and it is a different field: detectors record
`pos` as a character offset within the document, which is not a line number, so
it cannot be used as `startLine`. `_make_result` took `pos` and dropped it on
the floor for the same reason. `startColumn` is the correct home for it, and a
column that is absent (offset 0) must stay absent rather than claiming
column 1.
"""
from driftcheck.sarif import to_sarif


def _region(result, index=0):
    """The physical region SARIF published for one result."""
    return (
        result["runs"][0]["results"][index]["locations"][0]["physicalLocation"]["region"]
    )


def test_line_from_detector_reaches_start_line():
    """The defect: `line` was accepted by `_make_result` and never passed."""
    doc = to_sarif(
        {"docker_bases_drifts": [
            {"file": "Dockerfile", "line": 6, "image": "node", "tag": "latest"},
        ]}
    )
    assert _region(doc)["startLine"] == 6


def test_distinct_lines_stay_distinct_results():
    """Two stages on different lines must not collapse onto one location.

    This is the finding-count-preserving shape of the bug: both results exist,
    so a count-based guard stays green while both point at line 1.
    """
    doc = to_sarif(
        {"docker_bases_drifts": [
            {"file": "Dockerfile", "line": 6, "image": "node", "tag": "latest"},
            {"file": "Dockerfile", "line": 9, "image": "python", "tag": "latest"},
            {"file": "Dockerfile", "line": 12, "image": "alpine", "tag": "latest"},
        ]}
    )
    lines = [_region(doc, i)["startLine"] for i in range(3)]
    assert lines == [6, 9, 12]


def test_multistage_line_reaches_sarif():
    doc = to_sarif(
        {"docker_multistage_drifts": [
            {"file": "Dockerfile", "line": 3, "image": "node", "tags": ["18", "20"],
             "detail": "conflicting"},
        ]}
    )
    assert _region(doc)["startLine"] == 3


def test_missing_line_falls_back_to_one():
    """A finding with no line is still a finding; it just starts at line 1."""
    doc = to_sarif({"dependabot_drifts": [{"file": ".github/dependabot.yml", "detail": "x"}]})
    assert _region(doc)["startLine"] == 1


def test_zero_line_is_not_treated_as_a_location():
    """Line 0 is not a location SARIF can render.

    Detectors emit ``pos: 0`` as a "no offset recorded" placeholder, so a
    falsy check alone would let a 0 through when one is ever passed as a line.
    Clamping to 1 keeps every published region inside the file.
    """
    doc = to_sarif({"dependabot_drifts": [{"file": "a.yml", "line": 0, "detail": "x"}]})
    assert _region(doc)["startLine"] == 1


def test_negative_line_is_clamped():
    doc = to_sarif({"dependabot_drifts": [{"file": "a.yml", "line": -4, "detail": "x"}]})
    assert _region(doc)["startLine"] == 1


def test_non_integer_line_is_ignored():
    """A detector emitting a non-int must not raise and lose the document.

    The finding still has to be published: a malformed location is a rendering
    problem, and turning it into an exception would discard every other finding
    in the run with it.
    """
    doc = to_sarif(
        {
            "dependabot_drifts": [{"file": "a.yml", "line": "seven", "detail": "x"}],
            "rust_drifts": [{"file": "README.md", "doc_version": "1.9"}],
        }
    )
    results = doc["runs"][0]["results"]
    assert len(results) == 2
    assert _region(doc)["startLine"] == 1


def test_pos_becomes_start_column():
    """`pos` is a character offset, so it belongs in `startColumn`.

    No detector derives a line from it, so publishing it as `startLine` was
    never possible; the offset was simply discarded before.
    """
    doc = to_sarif({"actions_drifts": [{"file": "ci.yml", "pos": 12, "action": "actions/checkout"}]})
    assert _region(doc)["startColumn"] == 13


def test_absent_pos_does_not_invent_a_column():
    """A column of 1 for a finding with no offset claims precision it lacks."""
    doc = to_sarif({"dependabot_drifts": [{"file": "a.yml", "detail": "x"}]})
    assert "startColumn" not in _region(doc)


def test_line_wins_over_pos():
    """A detector that computed a line is more precise than a bare offset."""
    doc = to_sarif(
        {"docker_bases_drifts": [
            {"file": "Dockerfile", "line": 6, "pos": 40, "image": "node", "tag": "latest"},
        ]}
    )
    region = _region(doc)
    assert region["startLine"] == 6
    assert region["startColumn"] == 41


def test_region_shape_unchanged_for_every_drift_key():
    """Every result still publishes exactly one region, at a line >= 1.

    Guards the fix from silently changing the shape a consumer matches on.
    """
    from driftcheck.config import DRIFT_KEYS

    for key in DRIFT_KEYS:
        doc = to_sarif({key: [{"file": "f", "detail": "d"}]})
        region = _region(doc)
        assert region["startLine"] >= 1, key
        assert set(region) <= {"startLine", "startColumn"}, key