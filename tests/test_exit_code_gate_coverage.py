"""Every drift key the detector emits must be able to change the exit code.

The SARIF side of this defect class is already guarded by
``tests/test_sarif_coverage.py`` (landed with #475/#476). This file is the
missing half: the **exit-code** gate.

``cli.py`` builds its gate from ``DRIFT_KEYS``::

    all_drifts = {k: result.get(k, []) for k in DRIFT_KEYS}
    blocking_drifts = {k: v for k, v in all_drifts.items() if k not in INFORMATIONAL_DRIFTS}
    has_blocking = any(blocking_drifts.values())

``DRIFT_KEYS`` is a hand-maintained list in ``config.py``. A detector whose key
never made it into that list is detected, serialised into ``--json``, written
to ``--csv`` with ``severity=blocking`` and reported by ``--sarif`` at
``level=error`` -- and the process still exits 0. In CI that is a red build
rendered green, which is strictly worse than a crash because nothing in the
output says anything went wrong.

Reproduced end-to-end before this test existed: a fixture whose only finding
was ``frontmatter_drifts`` exited 0 in all five output modes (text, --json,
--csv, --sarif, --report) while the same finding appeared in SARIF at
``level=error``.

The AST scan below mirrors ``test_sarif_coverage._emitted_drift_keys`` and has
the same documented blind spot: plugin detectors build their keys at runtime
(``plugins.py`` -> ``f"plugin_{name}_drifts"``) and are merged in with
``result.update(...)``, so they never appear as a literal in ``detector.py``.
``test_runtime_plugin_key_reaches_exit_gate`` covers that path against the
real ``scan_repo`` instead of the parse.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.cli import INFORMATIONAL_DRIFTS
from driftcheck.config import DRIFT_KEYS

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


EMITTED = _emitted_drift_keys()


def test_detector_emits_keys() -> None:
    """Guard against the extraction silently finding nothing."""
    assert len(EMITTED) > 50, f"expected many drift keys, parsed {len(EMITTED)}"


@pytest.mark.parametrize("key", sorted(EMITTED))
def test_emitted_key_is_in_drift_keys(key: str) -> None:
    """A key absent from ``DRIFT_KEYS`` can never affect the exit code."""
    assert key in DRIFT_KEYS, (
        f"{key} is emitted by detector.py but absent from DRIFT_KEYS "
        f"(config.py), so a finding for it cannot change the exit code"
    )


@pytest.mark.parametrize("key", sorted(EMITTED))
def test_emitted_key_has_detector_info(key: str) -> None:
    """``DETECTOR_INFO`` drives ``--list-detectors`` and ``--only``."""
    from driftcheck.cli import DETECTOR_INFO

    assert key in DETECTOR_INFO, (
        f"{key} is emitted by detector.py but missing from DETECTOR_INFO, "
        f"so it cannot be selected with --only or listed by --list-detectors"
    )


def test_drift_keys_has_no_duplicates() -> None:
    """A repeated entry is a registry smell and skews any count-based claim."""
    seen: dict[str, int] = {}
    for key in DRIFT_KEYS:
        seen[key] = seen.get(key, 0) + 1
    dupes = sorted(k for k, n in seen.items() if n > 1)
    assert not dupes, f"DRIFT_KEYS contains duplicate entries: {dupes}"


def test_no_stale_drift_keys() -> None:
    """Every registered key must still be emitted, or the registry rots.

    A key in ``DRIFT_KEYS`` that ``scan_repo`` no longer returns is harmless
    at runtime (``result.get(k, [])`` yields ``[]``) but it is how the
    registry loses track of reality: nobody notices a detector being removed
    or renamed, and the list keeps claiming to describe the detectors.
    """
    stale = sorted(set(DRIFT_KEYS) - EMITTED)
    assert not stale, (
        f"DRIFT_KEYS lists keys that detector.py no longer emits: {stale}. "
        f"Plugin keys are registered at runtime and are expected to be absent "
        f"from this literal scan; everything else is stale."
    )


def test_informational_drifts_are_registered() -> None:
    """``INFORMATIONAL_DRIFTS`` only means something for registered keys."""
    unknown = sorted(INFORMATIONAL_DRIFTS - set(DRIFT_KEYS))
    assert not unknown, (
        f"INFORMATIONAL_DRIFTS references keys absent from DRIFT_KEYS: {unknown}"
    )


def test_sarif_severity_matches_cli_severity() -> None:
    """Both output paths must agree on what "informational" means.

    These were two independent literals that had drifted: the CLI listed six
    informational keys and SARIF listed four, so `changelog_drifts` and
    `typosquat_drifts` exited 0 while SARIF still reported them at
    `level=error`. Code Scanning then opened blocking alerts for findings the
    CLI treats as harmless. Severity is one fact, so both names now alias
    ``config.INFORMATIONAL_DRIFT_KEYS``; this test fails if that ever reverts
    to two copies.
    """
    from driftcheck import cli, sarif
    from driftcheck.config import INFORMATIONAL_DRIFT_KEYS

    assert cli.INFORMATIONAL_DRIFTS is INFORMATIONAL_DRIFT_KEYS, (
        "cli.INFORMATIONAL_DRIFTS must alias config.INFORMATIONAL_DRIFT_KEYS "
        "instead of declaring its own set"
    )
    assert sarif.INFORMATIONAL_TYPES is INFORMATIONAL_DRIFT_KEYS, (
        "sarif.INFORMATIONAL_TYPES must alias config.INFORMATIONAL_DRIFT_KEYS "
        "instead of declaring its own set"
    )


def test_runtime_plugin_key_reaches_exit_gate() -> None:
    """The AST scan above is blind to runtime-registered plugin keys.

    Rather than assert on the parse, this runs the real ``scan_repo`` over a
    fixture with a plugin detector installed and asserts the plugin key lands
    in the result dict. ``DRIFT_KEYS`` is a fixed list, so a plugin key is by
    construction outside the exit-code gate -- this test documents that as a
    known limitation rather than pretending the AST scan covers it. If a
    plugin finding must ever be able to fail a build, the fix is to make the
    gate open-ended over the result dict, not to add plugin keys to a list
    that can never stay current.
    """
    import textwrap

    from driftcheck.detector import scan_repo

    root = Path(__file__).resolve().parent / "_fixture_plugin_gate"
    try:
        root.mkdir()
        (root / ".driftcheck.toml").write_text(
            "[driftcheck]\n"
            "exclude_detectors = ['dependabot','lockfile','lineending']\n",
            encoding="utf-8",
        )
        plugin_dir = root / ".driftcheck_plugins"
        plugin_dir.mkdir()
        (plugin_dir / "gatecheck.py").write_text(
            textwrap.dedent('''
                def _probe(root, docs):
                    return [{"file": "README.md", "detail": "gate probe"}]

                def register():
                    return {"gatecheck": _probe}
            '''),
            encoding="utf-8",
        )
        result = scan_repo(root)
        plugin_keys = [k for k in result if k.startswith("plugin_")]
        assert plugin_keys, "fixture plugin produced no runtime key"
        assert all(k not in DRIFT_KEYS for k in plugin_keys), (
            "plugin keys appeared in DRIFT_KEYS; if plugin findings should be "
            "able to fail a build the gate needs reworking, not a list append"
        )
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_cli_exit_code_uses_only_registered_keys() -> None:
    """Pin the gate itself, so a future refactor cannot widen it silently.

    Asserts on the real ``main()`` exit code for a fixture whose only finding
    is a key that *is* registered (``lineending`` is excluded from the
    fixture, so nothing else can fire). This is the positive control for the
    parametrized membership tests above: they prove the registry is complete,
    this proves a registered key really does fail the build.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".driftcheck.toml").write_text(
            "[driftcheck]\n"
            "exclude_detectors = ['dependabot','lockfile']\n",
            encoding="utf-8",
        )
        (root / "rust-toolchain.toml").write_text(
            '[toolchain]\nchannel = "1.85.0"\n', encoding="utf-8"
        )
        (root / "Cargo.toml").write_text(
            '[package]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (root / "docs").mkdir()
        # frontmatter pins 1.60.0 against a 1.85.0 toolchain -> fires
        # frontmatter_drifts, which IS registered, so the build must fail.
        (root / "docs" / "README.md").write_text(
            "---\ntitle: x\nrust_version: 1.60.0\n---\n\n# docs\n", encoding="utf-8"
        )
        # encoding is explicit: the CLI guarantees UTF-8 stdout, and text=True
        # alone would decode with the ambient locale (cp1252 on a Windows
        # runner), killing the reader thread and leaving proc.stdout as None.
        proc = subprocess.run(
            [sys.executable, "-m", "driftcheck", str(root), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 1, (
            f"expected exit 1 for a registered blocking finding, got "
            f"{proc.returncode}: {proc.stdout[:400]}"
        )
        assert '"frontmatter_drifts"' in proc.stdout, (
            "expected the frontmatter finding in --json output"
        )