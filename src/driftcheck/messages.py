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

``describe_expected`` and ``describe_drift`` serve the remaining surfaces that
build a "documented value should be X" sentence. ``_print_report`` was
assembling that X from a hand-written list of six ``*_version`` field names, so
every other version field a detector emits fell off the end and the sentence
rendered with an empty target:

    - `README.md`: Python 3.9 → should be

``describe_pair`` extends the same subtraction to the payloads that name no
documented side at all, and returns both halves rather than one. ``--explain``
prints both, and it had no way to reach the pair on the majority of real
findings: 301 of 330 findings across 35 repos carry no ``doc_*`` field, so
``Actual``/``Expected``/``Diff``/``Fix`` rendered empty and unfixable while the
same finding printed correctly in the scan.

The same closed list had been copied into ``cli._render_generic_drift``,
``cli._print_csv`` and ``explain._extract_expected`` -- four lists over one open
key space, each free to fall out of date with the others, and each a place a
new detector's field name had to be added to by hand. All four call
``describe_expected`` now, so a field nobody listed is described rather than
dropped.

The expected value is therefore found by subtraction rather than by
enumeration: the *documented* side is the one with a stable vocabulary
(``doc_version``, ``doc_image``, ``doc_count`` and a ``tool`` to attribute it
to), so anything else carrying a value is the toolchain side by elimination. A
detector that names its field ``vault_image`` is described without a line being
added here.

Subtraction needs two closed sets to be worth anything, and both are about
driftcheck's own payload conventions rather than about detectors: the documented
side above, and ``_NON_VALUE_FIELDS`` for the fields that describe a finding
instead of a value. The second set is the fragile half -- a detector that emits
a label before its value (``package``, ``type``) needs that label excluded, and
an unknown label would be reported as the version. ``describe_expected``
therefore starts its scan *at* the documented field, so everything before it is
context whatever it is called.
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
#
# ``type`` and ``floor_source`` are here because the subtraction walks the
# payload in insertion order, and both detectors that emit them insert a label
# *before* the value they describe. ``python_version_drifts`` opens with
# ``type="doc"``, so without this entry the sentence reads
# "Python 3.9 → should be doc" -- a real detector, rendering a label as the
# version it wants. A label is never the answer, whatever it is called, which
# is why this set is about the *kind* of field rather than about detectors.
_NON_VALUE_FIELDS = frozenset({
    "file", "pos", "line", "tool", "kind", "url", "source", "type", "floor_source",
})


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


# Fields carrying the detector's own sentence about the finding instead of
# either side of a mismatch. ``detail`` is the spelling most detectors use and
# ``message`` the other one, and both are excluded from the pair for the same
# reason: "missing .gitattributes with * text=auto eol=lf" describes the finding,
# it is not one of the two values a reader should diff.
_SENTENCE_FIELDS = frozenset({"detail", "message"})


def _documented_field(d: dict) -> str | None:
    """The name of the field carrying the documented side of a mismatch."""
    return next((field for field in _DOCUMENTED_FIELDS if d.get(field)), None)


def describe_expected(d: object) -> str:
    """The value the toolchain declares, for a payload describing a mismatch.

    Found by subtraction: whatever carries a value and is neither the documented
    side nor finding metadata is what the toolchain actually says. That is the
    point of the exercise -- the alternative is a list of every ``*_version``
    field a detector might emit, which goes stale the moment a new detector
    names its payload differently, and the surfaces that each kept their own
    copy of it disagreed about which payloads they could read.

    The search starts *at* the documented field, not at the top of the payload.
    A detector is free to name the thing it is talking about
    (``package_version_drifts`` emits ``package="left-pad"``) and to emit that
    name before the documented value; scanning from the start would report the
    package name as the version the docs should carry. Everything before the
    documented side is context for the finding, and the counterpart follows it.

    Returns "" when the payload names no documented side: there is no mismatch
    to state, and a caller must not render half of one.
    """
    if not isinstance(d, dict):
        return ""

    documented_field = _documented_field(d)
    if documented_field is None:
        return ""

    at_documented_side = False
    for name, value in d.items():
        if name == documented_field:
            at_documented_side = True
        if not at_documented_side:
            continue
        if name in _DOCUMENTED_FIELDS or name in _NON_VALUE_FIELDS or value in _EMPTY:
            continue
        return str(value)
    return ""


def describe_pair(d: object) -> tuple[str, str] | None:
    """The two values a finding disagrees about, or None when it has none.

    The same subtraction ``describe_expected`` performs, extended to payloads
    that name no documented side. ``--explain`` needs both halves, and reading
    only the documented half is what left 89% of its findings with an empty
    ``Actual``, an empty ``Expected`` and no usable diff -- the scan printed the
    real values, in the payload, under names this surface had no way to reach.

    Derived, not enumerated, for the reason ``describe_expected``'s docstring
    gives: a closed list of the field names a detector picks goes stale the
    moment a new detector picks a different one. So the pair is read structurally
    -- every field that carries a value and is not location metadata, not finding
    metadata and not the detector's own sentence. What is left is what the payload
    is actually about.

    Order is the whole of the remaining rule. A payload's non-value fields
    (``action``, ``package``, ``instruction``) name the subject and lead; the two
    values that disagree follow them. Measured over 330 findings from 35 repos
    (``driftcheck --json`` over every checkout under ``repos/``), the last two
    surviving fields are the pair in every payload of that shape, and agree with
    ``describe_expected`` on all 29 payloads where that already worked. So
    ``{"action", "current", "suggested"}`` pairs ``current``/``suggested`` and
    never renders ``actions/checkout`` as a version.

    Scalars only. The one measured shape that breaks the rule is
    ``dependabot_incomplete``, whose two surviving fields are *lists* of
    ecosystem names: trailing-two pairs them, and ``str()`` renders
    ``"['github-actions', 'pip']"`` as a version on each side of a diff. A
    collection is part of the condition rather than one of two values to compare,
    so it does not count toward the pair and the caller renders the sentence --
    ``describe_finding`` already handles those payloads well.

    ponytail: trailing two, because every measured scalar payload follows it. A
    detector that emitted a third scalar value *after* the pair would need the
    rule to name the subject instead -- until one does, this is the version that
    needs no names.

    Returns None when fewer than two values survive: the finding names a subject
    and a condition (``kind`` + ``detail``) rather than two disagreeing values, so
    there is nothing to diff. The caller renders the detector's own sentence
    instead of inventing the missing half.
    """
    if not isinstance(d, dict):
        return None

    documented_field = _documented_field(d)
    if documented_field is not None:
        expected = describe_expected(d)
        if expected:
            return str(d[documented_field]), expected

    values = [
        str(value)
        for name, value in d.items()
        if name not in _LOCATION_FIELDS
        and name not in _NON_VALUE_FIELDS
        and name not in _SENTENCE_FIELDS
        and value not in _EMPTY
        # A list of names is the condition, not one of two values to compare;
        # ``str()`` of it is a Python repr, which is not a version.
        and isinstance(value, (str, int, float))
    ]
    if len(values) < 2:
        return None
    return values[-2], values[-1]


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

    documented_field = _documented_field(d)
    documented = d[documented_field] if documented_field else ""
    # `tool` names what the documented value is about, when the detector said.
    subject = d.get("tool") or ""
    return f"{subject} {documented} → should be {expected}".lstrip()
