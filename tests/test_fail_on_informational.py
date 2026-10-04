"""--fail-on-informational must promote informational drifts to blocking.

Issue #469: the flag and the matching ``fail_on_informational`` config key were
documented in the README but removed from the code, leaving the parser rejecting
a documented flag and the TOML key silently accepted and silently ignored.
"""

import subprocess
import sys
from pathlib import Path

from driftcheck.cli import _blocking_drifts

INFO_KEY = "lockfile_drifts"
BLOCKING_KEY = "python_drifts"


def _make_repo(tmp_path: Path) -> Path:
    """A repo whose only findings are informational: requirements.txt, no lockfile.

    .gitattributes is written on purpose: without it the lineending detector
    reports a *blocking* drift and every run would exit 1 whatever the flag
    under test says, which would make these tests pass for the wrong reason.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements.txt").write_text("requests==2.31.0\n")
    (root / "README.md").write_text("# P\n")
    (root / ".gitattributes").write_text("* text=auto eol=lf\n")
    return root


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *extra],
        capture_output=True,
        text=True,
    )


def test_config_key_defaults_to_false():
    from driftcheck.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["fail_on_informational"] is False


def test_blocking_drifts_excludes_informational_by_default():
    result = {INFO_KEY: ["requirements.txt"], BLOCKING_KEY: ["3.10"]}
    assert INFO_KEY not in _blocking_drifts(result)
    assert BLOCKING_KEY in _blocking_drifts(result)


def test_blocking_drifts_includes_informational_when_promoted():
    result = {INFO_KEY: ["requirements.txt"], BLOCKING_KEY: ["3.10"]}
    promoted = _blocking_drifts(result, fail_on_informational=True)
    assert INFO_KEY in promoted


def test_flag_is_accepted_and_changes_exit_code(tmp_path):
    root = _make_repo(tmp_path)
    assert _run(root).returncode == 0, "informational-only repo passes by default"
    assert _run(root, "--fail-on-informational").returncode == 1


def test_config_key_is_read_not_ignored(tmp_path):
    root = _make_repo(tmp_path)
    (root / ".driftcheck.toml").write_text("[driftcheck]\nfail_on_informational = true\n")
    assert _run(root).returncode == 1, "config key must promote informational drifts"


def test_json_output_respects_the_flag(tmp_path):
    root = _make_repo(tmp_path)
    assert _run(root, "--json", "--fail-on-informational").returncode == 1
    assert _run(root, "--json").returncode == 0