"""A legacy console codepage must not truncate the report.

Windows consoles still default to cp1252 on many runners, and cp1252 cannot
encode ``→``. Every printer emits ``→`` on nearly every finding, so the first
``print`` raised UnicodeEncodeError and killed the process mid-report:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'

The operator got a traceback instead of the findings. Worse, it is the exact
failure mode this tool exists to prevent: ``main`` prints first and returns the
gate's exit code afterwards, so the aborted print left the *text* surface
missing findings that ``--json``/``--csv``/``--sarif`` still carried, while the
build still failed. A clean report with a failing build, caused by the encoding
rather than by the repo.

CI caught this only as two red windows-latest legs; the same defect was invisible
on Linux, where UTF-8 is the default. These tests pin the behaviour so a future
refactor cannot reintroduce it, and they pin it in-process too -- asserting only
through a subprocess would leave the ``errors="replace"`` backstop untested.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.cli import _force_utf8_streams


def _run_cp1252(root: Path, *flags: str) -> subprocess.CompletedProcess:
    """Run the CLI with the encoding a Windows console would supply.

    ``PYTHONIOENCODING`` is what actually selects the stream encoding, so this
    reproduces the windows-latest condition on any host without a Windows box.
    """
    import os

    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *flags],
        capture_output=True,
        env=env,
    )


@pytest.fixture
def arrow_repo(tmp_path: Path) -> Path:
    """A repo whose findings render with ``→``, which cp1252 cannot encode."""
    (tmp_path / "README.md").write_text("# demo\nUse Python 0.34\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nrequires-python = ">=3.11"\n', encoding="utf-8"
    )
    return tmp_path


def test_text_output_is_complete_under_cp1252(arrow_repo: Path) -> None:
    """Every finding the JSON mode reports must survive a cp1252 console.

    Asserting on the finding COUNT rather than on the arrow is deliberate: the
    arrow itself is what cannot be encoded, so a fix that degraded ``→`` to
    ``?`` would pass a test that looked for the arrow while still telling the
    operator everything. What must not regress is the set of findings.
    """
    import json

    json_proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", str(arrow_repo), "--json"],
        capture_output=True,
    )
    blocking = [
        key
        for key, drifts in json.loads(json_proc.stdout).items()
        if key.endswith("_drifts") and isinstance(drifts, list) and drifts
    ]
    assert blocking, "fixture produced no findings; this test would prove nothing"

    proc = _run_cp1252(arrow_repo)

    # The regression's signature: the process died instead of reporting.
    assert b"UnicodeEncodeError" not in proc.stderr, (
        f"the printers still abort on a cp1252 console: "
        f"{proc.stderr.decode('utf-8', 'replace')[-800:]}"
    )
    assert proc.returncode == 1, (
        f"expected the drift gate to fail the build, got {proc.returncode}"
    )

    stdout = proc.stdout.decode("utf-8", "replace")
    printed = [line for line in stdout.splitlines() if line.startswith("driftcheck:")]
    assert printed, f"nothing was printed at all; stdout={stdout!r}"
    # stdout is UTF-8 regardless of the ambient codepage.
    assert "→" in stdout, (
        "output was re-encoded to the console codepage instead of UTF-8; "
        "piping to a file or another tool would then get mojibake"
    )
    assert any("Python 0.34" in line for line in printed), (
        f"the pyproject finding was lost from the text report: {printed}"
    )


def test_force_utf8_streams_reconfigures_a_cp1252_stream() -> None:
    """The helper fixes the streams it is given, not just the real ones.

    ``errors="replace"`` is the backstop for a codepage that still cannot take
    a character. Pinning it here means the guarantee does not rest on the
    subprocess test passing for the ordinary reason that UTF-8 can encode
    everything this fixture happens to produce.
    """
    stream = io.TextIOWrapper(
        io.BytesIO(), encoding="cp1252", errors="strict", newline="\n"
    )
    stdout, sys.stdout = sys.stdout, stream
    try:
        _force_utf8_streams()
        # Would raise UnicodeEncodeError under the original strict cp1252.
        stream.write("driftcheck: README.md: Python 0.34 → should be 3.11\n")
        stream.flush()
    finally:
        sys.stdout = stdout

    assert stream.encoding.lower().replace("-", "_") in {"utf_8", "utf8"}
    assert "→" in stream.buffer.getvalue().decode("utf-8")


def test_force_utf8_streams_tolerates_a_non_reconfigurable_stream() -> None:
    """A stream with no ``reconfigure`` is left alone rather than crashing.

    Replacing stdout with a plain object is legal and happens under some test
    harnesses and embedders. The report is worth more than the encoding, so the
    helper must not raise on its way to fixing the other stream.
    """

    class _NoReconfigure:
        def write(self, _data: str) -> int:
            return 0

        def flush(self) -> None:
            pass

    stdout, sys.stdout = sys.stdout, _NoReconfigure()  # type: ignore[assignment]
    try:
        _force_utf8_streams()  # must not raise
    finally:
        sys.stdout = stdout