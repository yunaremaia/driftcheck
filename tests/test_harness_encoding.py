"""The test harness must decode driftcheck's stdout as UTF-8, not the locale.

A Windows runner's ambient codepage is cp1252. The CLI now guarantees UTF-8 on
stdout, but a test that says only ``text=True`` decodes the child's bytes with
that ambient locale. CP1252 cannot represent UTF-8's continuation bytes, so the
failure lands in a place with a very misleading signature:

    File "subprocess.py", line 1599, in _readerthread
      buffer.append(fh.read())
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 72

That exception kills the *reader thread*, not the call. ``run()`` returns a
CompletedProcess whose ``stdout`` was never appended to -- so ``stdout`` is
**None**. The test then fails far from the cause, as
``TypeError: argument of type 'NoneType' is not iterable`` on a line that merely
reads ``proc.stdout``, and a naive fix would make it pass by asserting nothing.

That is the whole class of bug these tests pin: an undecodable stream must fail
loudly at the decode, never silently become an empty/None buffer that a
substring assertion quietly accepts.

``PYTHONIOENCODING`` sets the *child's* encoding, and ``encoding=`` sets the
*parent's* decode -- they are independent, which is exactly why one of them
being wrong is invisible until the other side changes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

UTF8 = "utf-8"
# Byte 0x9d is undefined in cp1252 and is a UTF-8 continuation byte, so it is
# the cheapest way to reproduce the reader-thread death deterministically.
CP1252 = "cp1252"


@pytest.fixture
def cli_repo(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# demo\nUse Python 0.34\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nrequires-python = ">=3.11"\n', encoding="utf-8"
    )
    return tmp_path


def _run(root: Path, *flags: str, parent_encoding: str | None) -> subprocess.CompletedProcess:
    """Run the CLI, optionally decoding the way a Windows runner would."""
    kwargs: dict = {"capture_output": True, "text": True}
    if parent_encoding is not None:
        kwargs["encoding"] = parent_encoding
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *flags], **kwargs
    )


def _cp1252_decode_went_wrong(
    proc: subprocess.CompletedProcess | None, exc: BaseException | None
) -> str:
    """Classify how a cp1252 parent handled UTF-8 output, per platform.

    CPython reads a captured pipe in a *reader thread*. Whether a decode error
    surfaces to the caller or is swallowed by that thread is platform- and
    build-dependent, and both shapes are the same defect:

    * POSIX builds decode in ``communicate`` and raise to the caller;
    * Windows builds die in ``_readerthread``, so ``run()`` returns normally
      with ``stdout`` never appended -- i.e. ``None``.

    Asserting on one shape is what made this test red on exactly the platform
    it exists to model. The invariant worth pinning is the one that matters: the
    decode never silently yields correct text.
    """
    if exc is not None:
        assert isinstance(exc, UnicodeDecodeError), f"unexpected {exc!r}"
        return "raised"
    # No exception reached us. Then the thread must have died and left stdout
    # unset; a populated stdout would mean the bytes decoded correctly, which
    # would mean the cp1252 model no longer reproduces anything.
    assert proc is not None and proc.stdout is None, (
        "the cp1252 decode neither raised nor dropped the buffer; got "
        f"{proc.stdout[:200]!r}. If CPython ever made this decode lenient, "
        "revisit the encoding= argument this file justifies."
    )
    return "thread_died"


def test_cp1252_parent_decode_never_yields_correct_text(cli_repo: Path) -> None:
    """Pins WHY the harness must pass ``encoding``: the locale decode really dies.

    ``--report`` is the mode that proves it, because it carries emoji rather
    than the arrows of the text mode. ``❌`` (U+274C) is UTF-8 ``e2 9d 8c``, and
    the ``9d`` is undefined in cp1252 -- which is the exact byte and position
    CI reported. The plain text mode only carries ``→`` (``e2 86 92``), whose
    bytes cp1252 happens to map, so it comes back as mojibake instead of
    raising: the same defect, a much quieter symptom.
    """
    exc: BaseException | None = None
    try:
        proc = _run(cli_repo, "--report", parent_encoding=CP1252)
    except UnicodeDecodeError as raised:  # POSIX CPython
        proc, exc = None, raised

    assert _cp1252_decode_went_wrong(proc, exc) in {"raised", "thread_died"}


def test_mojibake_is_the_quiet_variant_of_the_same_defect(cli_repo: Path) -> None:
    """Text mode does not raise -- it silently returns wrong characters.

    Asserting on the arrow here would catch the corruption, and is the reason
    the fix must not be "decode leniently": a lenient decode returns a report
    the operator reads without noticing anything is wrong.
    """
    exc: BaseException | None = None
    try:
        proc = _run(cli_repo, parent_encoding=CP1252)
    except UnicodeDecodeError as raised:  # POSIX CPython
        proc, exc = None, raised

    if exc is not None or proc is None or proc.stdout is None:
        # This platform drops the buffer instead of mangling it; covered as
        # "thread_died" by the sibling test.
        assert _cp1252_decode_went_wrong(proc, exc) == "thread_died" or exc is not None
        return

    assert "→" not in proc.stdout, (
        "expected mojibake rather than a clean arrow; if this now decodes "
        "cleanly the cp1252 reproduction no longer models a Windows runner"
    )
    assert proc.stdout.count("�") or "â" in proc.stdout, (
        f"expected visibly mangled output, got: {proc.stdout[:200]!r}"
    )


def test_utf8_parent_decode_returns_the_full_report(cli_repo: Path) -> None:
    """With the explicit decode the report is complete and never None.

    The NoneType guard is the point: an assertion of the form
    ``x in proc.stdout`` raises TypeError on None, but a test that used
    ``proc.stdout or ""`` would pass with an empty report, which is the failure
    this whole class of bug produces.
    """
    proc = _run(cli_repo, parent_encoding=UTF8)

    assert proc.stdout is not None, (
        "reader thread produced no buffer; the child emitted undecodable bytes "
        f"for a UTF-8 parent. stderr={proc.stderr.decode('utf-8', 'replace')[-400:]}"
    )
    assert proc.returncode == 1, f"expected the drift gate to fire, got {proc.returncode}"
    assert "Python 0.34" in proc.stdout
    assert "→" in proc.stdout, "the arrow survived the round trip"


def test_json_mode_round_trips_non_ascii_through_the_harness(cli_repo: Path) -> None:
    """A finding whose text is non-ASCII must survive decode, not get mangled.

    ``json.loads`` would accept mojibake without complaint -- it is valid JSON
    either way -- so without this the corruption would reach an assertion as a
    silent string mismatch far from the decode that caused it.
    """
    proc = _run(cli_repo, "--json", parent_encoding=UTF8)

    assert proc.stdout is not None
    payload = json.loads(proc.stdout)
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "�" not in rendered, (
        "a replacement character reached the payload, so the decode lost data: "
        f"{rendered[:400]}"
    )