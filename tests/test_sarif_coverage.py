"""Every drift key the detector emits must be reachable in SARIF output.

Regression guard for the silent-drop defect: ``to_sarif`` gates on two
independent structures -- the ``drift_keys`` list it iterates and the
``DRIFT_RULES`` mapping it looks up. A detector whose key is missing from
either one still prints findings normally and then vanishes from ``--sarif``,
with nothing in the output to say so. Several externally contributed
detectors were unreachable this way.

These tests fail loudly when a new detector is added to ``detector.py``
without the matching SARIF wiring.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from driftcheck import sarif  # noqa: F401  (imported for module-level contract)
from driftcheck.sarif import DRIFT_RULES

_SRC = Path(__file__).resolve().parents[1] / "src" / "driftcheck"


def _emitted_drift_keys() -> set[str]:
    """Drift keys assigned into the result dict in ``detector.py``."""
    tree = ast.parse((_SRC / "detector.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if key.value.endswith("_drifts"):
                    keys.add(key.value)
    return keys


def _sarif_drift_keys() -> set[str]:
    """The ``drift_keys`` list ``to_sarif`` iterates over."""
    tree = ast.parse((_SRC / "sarif.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "drift_keys":
                    return set(ast.literal_eval(node.value))
    raise AssertionError("drift_keys list not found in sarif.py")


EMITTED = _emitted_drift_keys()
SARIF_KEYS = _sarif_drift_keys()


def test_detector_emits_keys():
    """Guard against the extraction silently finding nothing."""
    assert len(EMITTED) > 50, f"expected many drift keys, parsed {len(EMITTED)}"


@pytest.mark.parametrize("key", sorted(EMITTED))
def test_emitted_key_has_drift_rule(key: str) -> None:
    """Every emitted key needs a rule, or ``to_sarif`` drops it silently."""
    assert key in DRIFT_RULES, (
        f"{key} is emitted by detector.py but has no DRIFT_RULES entry, "
        f"so it never reaches SARIF output"
    )


@pytest.mark.parametrize("key", sorted(EMITTED))
def test_emitted_key_is_in_drift_keys_list(key: str) -> None:
    """Every emitted key must be on the list ``to_sarif`` walks."""
    assert key in SARIF_KEYS, (
        f"{key} is emitted by detector.py but absent from the drift_keys "
        f"list, so it never reaches SARIF output"
    )


@pytest.mark.parametrize("key", sorted(DRIFT_RULES))
def test_drift_rule_is_well_formed(key: str) -> None:
    """Rules are unpacked as ``(rule_id, name, description)``."""
    rule = DRIFT_RULES[key]
    assert isinstance(rule, tuple), f"{key} rule must be a tuple, got {type(rule)}"
    assert len(rule) == 3, (
        f"{key} must be a 3-tuple (rule_id, name, description); "
        f"got {len(rule)} element(s) -- a short tuple raises or mangles output"
    )
    assert all(isinstance(part, str) and part.strip() for part in rule), (
        f"{key} rule fields must all be non-empty strings"
    )


def test_rule_ids_are_unique() -> None:
    """Duplicate rule ids collapse in Code Scanning."""
    seen: dict[str, str] = {}
    for key, rule in DRIFT_RULES.items():
        rule_id = rule[0]
        assert rule_id not in seen, (
            f"rule id {rule_id!r} shared by {seen.get(rule_id)} and {key}"
        )
        seen[rule_id] = key


def test_drift_keys_have_rules() -> None:
    """No dead entries on the walk list."""
    orphans = sorted(SARIF_KEYS - set(DRIFT_RULES))
    assert not orphans, f"drift_keys entries without a DRIFT_RULES rule: {orphans}"


def test_to_sarif_gate_covers_every_emitted_key() -> None:
    """The ``to_sarif`` gate must not skip any emitted detector.

    ``to_sarif`` reaches a finding only when the key is on ``drift_keys``
    *and* present in ``DRIFT_RULES``; the third condition is that the rule is
    a 3-tuple, since it is unpacked as ``(rule_id, name, description)``. All
    three are asserted directly here and per-key above.

    A full ``to_sarif`` round trip is deliberately not attempted: message
    rendering reads detector-specific fields that no synthetic payload can
    supply, and that rendering is covered by each detector's own tests.
    """
    for key in EMITTED:
        assert key in SARIF_KEYS, f"{key} is skipped by the drift_keys walk"
        assert key in DRIFT_RULES, f"{key} is skipped by the DRIFT_RULES lookup"
        assert len(DRIFT_RULES[key]) == 3, f"{key} rule cannot be unpacked"