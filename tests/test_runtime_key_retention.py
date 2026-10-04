"""A drift key registered at runtime must not be dropped before the user sees it.

``tests/test_exit_code_gate_coverage.py`` (#477) closed the exit-code half of
the retention defect for every key that is a **literal** in ``detector.py``.
``tests/test_sarif_coverage.py`` (#475/#476) closed the SARIF half, and made it
*open-ended*: ``to_sarif`` walks its curated list and then whatever other
``*_drifts`` keys the result contains, so a key with no curated rule gets a
derived one instead of being discarded.

The CLI gate was never given the same treatment. ``cli.py`` builds its
enumeration from ``DRIFT_KEYS`` -- a fixed list in ``config.py`` -- at every
site that decides what counts as a finding::

    blocking = {k: result.get(k, []) for k in DRIFT_KEYS if k not in INFORMATIONAL_DRIFTS}

Plugin detectors do not appear in that list and *cannot* appear in it: their
key is built at runtime by ``plugins.run_plugin_detectors`` as
``f"plugin_{name}_drifts"`` and merged in with ``result.update(...)``. So a
plugin finding is detected, serialised into ``--json``, written to ``--csv``
with ``severity=blocking`` and reported by ``--sarif`` at ``level=error`` --
and the process still exits 0. In CI that is a red build rendered green, and
it is strictly worse than a crash because nothing in the output says anything
went wrong.

The same enumeration also backs the text printer. ``cli._print_blocking_drifts``
has a generic ``plugin_*`` branch, but it iterates ``all_drifts``, which is
built the same fixed way, so the branch is unreachable for the keys it was
written for. ``_print_report`` has the same problem and reports "0 drifts".

Reproduced end-to-end before this file existed, with a fixture repo whose only
finding came from a plugin::

    driftcheck --json   -> {"plugin_widget_drifts": [...]}   exit 0
    driftcheck --csv    -> README.md,plugin_widget_drifts,,,blocking,...
                                                                   exit 0
    driftcheck --sarif  -> results[0].ruleId=plugin_widget-drift
                           results[0].level=error              exit 0
    driftcheck          -> "driftcheck: no toolchain version found"
                                                                   exit 0
    driftcheck --report -> 0 drifts                             exit 0

These tests drive the real CLI in a subprocess over a real fixture directory on
disk, because the defect is only observable in the process exit status: reading
the source shows a list, running it shows the verdict.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_PLUGIN = """\
def find_widget_drift(root, docs):
    return [{"file": "README.md", "detail": "widget version mismatch"}]


def register():
    return {"widget": find_widget_drift}
"""

_CONFIG = """\
[driftcheck]
exclude_detectors = [
    "dependabot",
    "lockfile",
    "freshness",
    "typosquat",
    "lineending",
]
"""


@pytest.fixture
def plugin_repo(tmp_path: Path) -> Path:
    """A repo with no toolchain and no curated detector able to fire.

    Everything except the plugin is absent on purpose: if a curated detector
    contributed a finding it would gate the exit code by itself and this
    fixture would stop isolating the runtime key.
    """
    root = tmp_path / "plugin_repo"
    (root / ".driftcheck_plugins").mkdir(parents=True)
    (root / ".driftcheck.toml").write_text(_CONFIG, encoding="utf-8")
    (root / ".driftcheck_plugins" / "widget_plugin.py").write_text(
        _PLUGIN, encoding="utf-8"
    )
    (root / "README.md").write_text("# plugin fixture\n", encoding="utf-8")
    return root


def _run(root: Path, *flags: str) -> subprocess.CompletedProcess:
    # encoding is explicit because the CLI now guarantees UTF-8 on stdout.
    # text=True alone decodes with the *ambient* locale, which on a Windows
    # runner is cp1252: the reader thread then dies on a multi-byte character,
    # the buffer is never appended, and proc.stdout silently becomes None --
    # so a passing assertion would compare against None instead of the report.
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_plugin_finding_reaches_the_result_dict(plugin_repo: Path) -> None:
    """Guard for the fixture itself: without this row every test below is void.

    A test that passes because its fixture did not fire proves nothing, so the
    retention claim is only made after the key is observed in real output.
    """
    proc = _run(plugin_repo, "--json")
    result = json.loads(proc.stdout)
    assert result.get("plugin_widget_drifts"), (
        "fixture plugin produced no runtime key; the remaining tests in this "
        f"file would pass vacuously. stdout was: {proc.stdout[:400]}"
    )


@pytest.mark.parametrize("flag", ["--json", "--csv", "--sarif", "--report", ""])
def test_runtime_key_breaks_the_build_in_every_mode(
    plugin_repo: Path, flag: str
) -> None:
    """Every output mode must reach the same verdict.

    The point is not that one mode is right and another is wrong. It is that
    ``--csv`` printing ``severity=blocking`` and ``--sarif`` printing
    ``level=error`` while the process exits 0 is a single defect seen from
    five directions, and each mode has to agree with the others.
    """
    proc = _run(plugin_repo, *([flag] if flag else []))
    assert proc.returncode == 1, (
        f"a plugin finding is a real finding, but driftcheck exited "
        f"{proc.returncode} in mode {flag or 'text'!r}. --csv reports it as "
        f"blocking and --sarif reports it at level=error, so every mode must "
        f"fail. stdout: {proc.stdout[:400]} stderr: {proc.stderr[:400]}"
    )


def test_csv_severity_and_exit_code_agree(plugin_repo: Path) -> None:
    """The invariant from the other side: no output may claim blocking + exit 0.

    This is the shape a reviewer can check without knowing anything about
    plugins -- if any line of the CSV says ``blocking``, the run failed.
    """
    proc = _run(plugin_repo, "--csv")
    blocking_rows = [
        line for line in proc.stdout.splitlines() if ",blocking," in line
    ]
    assert blocking_rows, (
        "expected the plugin finding in --csv output; fixture did not fire: "
        f"{proc.stdout[:400]}"
    )
    assert proc.returncode == 1, (
        f"--csv reported a blocking finding but the process exited "
        f"{proc.returncode}: {blocking_rows}"
    )


def test_sarif_level_and_exit_code_agree(plugin_repo: Path) -> None:
    """``level=error`` in SARIF and a non-zero exit code are the same statement.

    A SARIF ``level=error`` result that ships alongside exit 0 opens a blocking
    GitHub Code Scanning alert that the CLI itself considers harmless, which is
    how a team ends up disabling the upload to silence it.
    """
    proc = _run(plugin_repo, "--sarif")
    doc = json.loads(proc.stdout)
    results = doc["runs"][0]["results"]
    assert results, "expected SARIF results; fixture did not fire"
    errors = [r for r in results if r.get("level") == "error"]
    assert errors, f"expected a level=error result, got {results}"
    assert proc.returncode == 1, (
        f"SARIF reported {len(errors)} level=error result(s) but the process "
        f"exited {proc.returncode}"
    )


def test_plugin_finding_is_printed_in_text_mode(plugin_repo: Path) -> None:
    """The generic plugin branch in the text printer must be reachable.

    ``_print_blocking_drifts`` has a ``plugin_*`` handler, but it iterates the
    ``all_drifts`` dict that is built from the fixed key list, so for a runtime
    key the branch can never fire and the user is told the repo is clean.
    """
    proc = _run(plugin_repo)
    assert proc.returncode == 1
    assert "widget" in proc.stdout, (
        "expected the plugin finding in text output; the run reported no "
        f"toolchain instead: {proc.stdout[:400]}"
    )


def test_plugin_finding_appears_in_the_report(plugin_repo: Path) -> None:
    """``--report`` counts findings from the same fixed list, so it said 0."""
    proc = _run(plugin_repo, "--report")
    assert proc.returncode == 1
    assert "Total drifts:** 0" not in proc.stdout, (
        "--report reported no drifts while the plugin found one: "
        f"{proc.stdout[:400]}"
    )