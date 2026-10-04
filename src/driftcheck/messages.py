"""Shared one-line rendering for a finding with no hand-written formatter.

Both report surfaces hand-format the drift keys whose payload shape they know:
``sarif._drift_message`` builds the ``message.text`` Code Scanning shows, and
``cli._render_generic_drift`` builds the ``--json``-less human line. Each kept
its own fallback for everything else, and both fallbacks dumped the raw payload
-- ``str(d)`` -- so a detector whose key had no bespoke branch was reported as a
Python dict repr rather than a sentence. In SARIF that repr is the whole alert
text an operator reads in the Code Scanning UI.

``describe_finding`` is that fallback, in one place, so the surfaces cannot
disagree about how a key they do not special-case is described. It is generic by
construction: it reads the payload rather than the drift key, so a detector
merged tomorrow renders sensibly without a line being added here.

``describe_expected`` and ``describe_drift`` serve the ``--report`` surface,
which is still the one that builds a "documented value should be X" sentence.
It had been assembling that X from a hand-written list of six ``*_version``
field names, so every other version field a detector emits fell off the end and
the sentence rendered with an empty target. The same closed list appeared in
``cli._render_generic_drift``, ``cli._print_csv`` and ``explain._extract_expected``
-- four copies of a registry over the same open key space, none of them able to
see a field the others had not listed.

The expected value is therefore found by subtraction rather than by
enumeration: the *documented* side is the one with a stable vocabulary
(``doc_version``, ``doc_image``, ``doc_count`` and a ``tool`` to attribute it
to), so anything else carrying a value is the toolchain side by elimination. A
detector that names its field ``vault_image`` is described without a line being
added here.
"""

from __future__ import annotations

# Where the finding lives, and where in the file. Both are carried on every
# result as location metadata and the surfaces render them separately, so they
# are dropped from the payload summary rather than repeated in it.
_LOCATION_FIELDS = frozenset({"file", "pos", "line"})

# A field worth naming in the summary: carrying a real value, not a placeholder.
# Detectors emit absent values as ""/None/0, and "package=" tells the reader
# nothing that omitting it would not.
_EMPTY = (None, "", 0)

# Fields naming the *documented* side of a mismatch. This vocabulary is small
# and closed on purpose: it is the side driftcheck controls, so knowing it lets
# the toolchain side be found by elimination instead of by a list of every name
# a detector might pick. Anything outside this set that carries a value is
# treated as what the toolchain actually declares.
_DOCUMENTED_FIELDS = ("doc_version", "doc_image", "doc_count")

# Fields that describe the finding rather than either side of the mismatch.
# ``detail`` is handled first and so never reaches the subtraction; the rest
# would otherwise read as "the actual value", which they are not.
_NON_VALUE_FIELDS = frozenset({"file", "pos", "line", "tool", "kind", "url", "source"})


def describe_finding(d: object) -> str:
    """Describe one finding without needing a per-detector formatter.

    Prefers the detector's own ``detail``, which is the sentence it wrote for a
    human. Failing that, names the fields that carry a value, which reads as a
    summary rather than a repr. A payload with neither is described by its
    repr, because there is nothing left to describe.
    """
    if not isinstance(d, dict):
        return str(d)

    detail = d.get("detail")
    if detail:
        return str(detail)

    fields = [
        f"{name}={value}"
        for name, value in d.items()
        if name not in _LOCATION_FIELDS and value not in _EMPTY
    ]
    if fields:
        return " ".join(fields)

    return str(d)


def describe_expected(d: object) -> str:
    """The value the toolchain declares, for a payload describing a mismatch.

    Found by subtraction: whatever carries a value and is neither the documented
    side nor finding metadata is what the toolchain actually says. That is the
    point of the exercise -- the alternative is a list of every ``*_version``
    field a detector might emit, which goes stale the moment a new detector
    names its payload differently, and the surfaces that each kept their own
    copy of it disagreed about which payloads they could read.

    Returns "" when the payload names no documented side: there is no mismatch
    to state, and a caller must not render half of one.
    """
    if not isinstance(d, dict):
        return ""

    documented = next(
        (d[field] for field in _DOCUMENTED_FIELDS if d.get(field)), None
    )
    if not documented:
        return ""

    for name, value in d.items():
        if name in _DOCUMENTED_FIELDS or name in _NON_VALUE_FIELDS or value in _EMPTY:
            continue
        return str(value)
    return ""


def describe_drift(d: object) -> str:
    """One line for a finding, preferring a mismatch sentence when it can.

    Three levels, each a strict improvement over the one after it: the
    detector's own ``detail``; the "documented X should be Y" sentence when the
    payload has both sides; the shared field summary. The middle level is only
    taken when ``describe_expected`` found a target, because the sentence with
    an empty target ("Python 3.9 should be") reads as a rendering bug rather
    than the drift it is reporting.
    """
    if not isinstance(d, dict):
        return str(d)

    detail = d.get("detail")
    if detail:
        return str(detail)

    expected = describe_expected(d)
    if not expected:
        return describe_finding(d)

    documented = next(
        (d[field] for field in _DOCUMENTED_FIELDS if d.get(field)), None
    )
    # `tool` names what the documented value is about, when the detector said.
    subject = d.get("tool") or ""
    return f"{subject} {documented} → should be {expected}".lstrip()
