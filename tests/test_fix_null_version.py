"""Regression: --fix must not crash when a drift has no version string to rewrite.

Detectors emit ``doc_version: None`` whenever the documentation file has no
version token to compare. In GO_RE, the second alternative puts the version in
the ``ver2`` group while the detector reads only ``ver``, so a README sentence
like "This repo targets Go 1.19." produces a drift with ``doc_version=None``.
``fix_in_file`` used to feed that ``None`` straight into ``str.replace``,
raising TypeError and killing the whole ``--fix`` run -- so *nothing* got
fixed, including files that had a perfectly good version string.
"""
from __future__ import annotations

from pathlib import Path

from driftcheck.detector import scan_repo
from driftcheck.detectors.fix import apply_fixes


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _fake_repo(tmp_path: Path) -> None:
    _write(tmp_path / "go.mod", "module example.com/demo\n\ngo 1.21\n")
    # "Go 1.19" here matches GO_RE's second alternative (the `ver2` group), so
    # the detector reports doc_version=None for this file.
    _write(tmp_path / "README.md", "# demo\n\nThis repo targets Go 1.19.\n")
    # A sibling drift with a real version string: it must still be rewritten
    # even though the README above aborts the whole run today.
    _write(tmp_path / "CONTRIBUTING.md", "# contributing\n\nInstall Go 1.19 to build.\n")


def test_fix_survives_null_doc_version_and_fixes_the_rest(tmp_path):
    _fake_repo(tmp_path)

    result = scan_repo(tmp_path)
    assert any(d.get("doc_version") is None for d in result.get("go_drifts", [])), (
        "fixture must produce a go drift with a null doc_version, "
        "otherwise this test proves nothing"
    )

    fixed = apply_fixes(tmp_path, result)  # used to raise TypeError

    # The file with no version string has nothing to rewrite, so it is skipped.
    assert "README.md" not in fixed
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == (
        "# demo\n\nThis repo targets Go 1.19.\n"
    )
    # ...and the rest of the tree is still fixed.
    assert "CONTRIBUTING.md" in fixed
    assert "1.21" in (tmp_path / "CONTRIBUTING.md").read_text(encoding="utf-8")


def test_fix_in_file_returns_false_for_missing_version(tmp_path):
    """The shared helper is the single guard point for every caller."""
    from driftcheck.detectors.fix import apply_fixes as _af  # noqa: F401  (import sanity)

    target = tmp_path / "docs.md"
    _write(target, "Install Rust 1.93.0\n")

    result = {"rust_drifts": [{"file": "docs.md", "doc_version": None, "toolchain_version": "1.96.1"}]}

    assert apply_fixes(tmp_path, result) == []
    assert target.read_text(encoding="utf-8") == "Install Rust 1.93.0\n"