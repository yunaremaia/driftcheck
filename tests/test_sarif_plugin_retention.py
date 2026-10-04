"""A finding that ``scan_repo`` detects must appear in ``--sarif`` output.

``to_sarif`` walks a hand-maintained ``drift_keys`` list and looks each key up
in ``DRIFT_RULES``. Any finding whose key is in neither is skipped with a bare
``continue`` -- no warning, no placeholder -- so the detector's result exists
in ``--json`` and vanishes from the SARIF document that feeds GitHub Code
Scanning.

``tests/test_sarif_coverage.py`` guards the built-in detectors, but it derives
its key set from ``ast.Dict`` literals in ``detector.py``. Plugin detectors are
registered at runtime under an f-string key (``f"plugin_{name}_drifts"``) and
merged in with ``result.update(plugin_results)``, so no literal exists for that
test to find and the plugin path is structurally invisible to it.

These tests cover the runtime path, so a plugin finding is asserted to survive
into the SARIF document rather than being dropped.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_SOURCE = '''\
def find_my_drift(root, docs):
    return [{"file": "README.md", "detail": "plugin found real drift"}]


def register():
    return {"my_dector": find_my_drift}
'''


def _make_repo(root: Path) -> None:
    plugins = root / ".driftcheck_plugins"
    plugins.mkdir(parents=True)
    (plugins / "my_detector.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")


def _run(root: Path, flag: str) -> tuple[dict, int]:
    # encoding is explicit: the CLI guarantees UTF-8 stdout, and text=True
    # alone would decode with the ambient locale (cp1252 on a Windows runner),
    # killing the reader thread and leaving proc.stdout as None.
    proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), flag],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode in (0, 1), proc.stderr
    return json.loads(proc.stdout), proc.returncode


def test_plugin_finding_is_detected(tmp_path: Path) -> None:
    """Control: the fixture must actually fire, or the test proves nothing."""
    _make_repo(tmp_path)
    detected, _ = _run(tmp_path, "--json")
    assert detected["plugin_my_dector_drifts"], (
        "fixture did not fire -- plugin detection is broken, so the SARIF "
        "assertions below would pass vacuously"
    )


def test_plugin_finding_reaches_sarif_output(tmp_path: Path) -> None:
    """A detected plugin finding must produce a SARIF result, not vanish."""
    _make_repo(tmp_path)
    detected, _ = _run(tmp_path, "--json")
    assert detected["plugin_my_dector_drifts"]

    doc, _ = _run(tmp_path, "--sarif")
    results = doc["runs"][0]["results"]

    assert results, (
        "scan_repo detected plugin_my_dector_drifts but --sarif emitted no "
        "results at all -- to_sarif silently dropped the finding"
    )
    messages = [r["message"]["text"] for r in results]
    assert any("plugin found real drift" in m for m in messages), (
        f"plugin finding missing from SARIF results; got {messages}"
    )


def test_unknown_drift_key_is_not_silently_dropped(tmp_path: Path) -> None:
    """An unregistered ``*_drifts`` key must still surface, as a fallback rule.

    This is the general shape of the defect: ``to_sarif`` must never discard a
    finding just because no curated rule exists for it.
    """
    from driftcheck.sarif import to_sarif

    doc = to_sarif(
        {
            "plugin_some_unregistered_drifts": [
                {"file": "README.md", "detail": "unregistered key finding"}
            ]
        },
        version="0.0.0",
    )
    results = doc["runs"][0]["results"]
    assert len(results) == 1, (
        f"unregistered drift key produced {len(results)} SARIF results, "
        "expected 1 -- the finding was dropped"
    )
    assert results[0]["ruleId"]
    assert "unregistered key finding" in results[0]["message"]["text"]


def test_sarif_gate_test_cannot_see_runtime_keys() -> None:
    """Documents why the ast-based guard cannot cover plugin findings.

    If plugin keys ever become literals in ``detector.py``, this test fails and
    points at the coverage gap it used to leave.
    """
    # Loaded by path, not by ``from tests....``: ``tests/`` is not a package,
    # so that import only resolves when the repo root happens to be on
    # sys.path -- which is true locally and false in CI.
    coverage_mod = importlib.util.spec_from_file_location(
        "_sarif_coverage_guard",
        Path(__file__).resolve().parent / "test_sarif_coverage.py",
    )
    assert coverage_mod is not None and coverage_mod.loader is not None
    module = importlib.util.module_from_spec(coverage_mod)
    coverage_mod.loader.exec_module(module)

    assert not any(k.startswith("plugin_") for k in module.EMITTED), (
        "plugin drift keys are now visible to the ast-based guard; the "
        "runtime-path tests in this file should be reconciled with it"
    )