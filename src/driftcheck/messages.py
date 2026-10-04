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
