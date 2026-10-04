"""The `--report` markdown must describe findings, not print their dict repr.

`_print_report` is the surface CI renders into a job summary and a human pastes
into a PR comment, and it is the one output surface still carrying the
closed-list-over-an-open-key-space defect that #475/#476/#481 fixed elsewhere.
It has two copies of the flaw, and neither is a gate the way the others were:

* the blocking branch ended in ``print(f"- \\`{file}\\`: {d}")`` -- the payload's
  own ``repr``. Any finding with no ``detail`` reached it, which is every
  plugin detector (its key is born at runtime, so no branch can exist for it)
  plus every curated detector that reports structured fields instead of a
  sentence. Measured on a real run::

      - `README.md`: {'file': 'README.md', 'rule': 'probe-rule', 'expected': '2.0', 'pos': 0}
      - `requirements.txt`: {'file': 'requirements.txt', 'package': 'requests', 'pinned_version': '2.31.0', ...}

* the informational branch used ``d.get("detail", str(d))`` -- the same repr
  one function over.

There is a third consequence on the same lines, quieter than the repr: the
"documented value should be" sentence is built from a hand-written list of six
``*_version`` field names. Every other version field a detector emits falls off
the end of it, so the sentence renders with an empty target --

    - `README.md`: Python 3.9 → should be

-- which reads as a rendering bug rather than the drift it is reporting. 32 of
the 38 version-ish fields the other surfaces look up were unreachable here.

These tests drive the real CLI, because the defect only exists in emitted
output: ``_print_report`` is reached through ``main`` and a unit test of the
payload would pass against the broken code.

The unit-level tests for the generic helpers this fix introduces live in
``test_messages_pairing.py``, so that importing a name that does not exist yet
cannot stop this module from being collected -- a collection error would hide
the RED these tests are here to demonstrate.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.messages import describe_finding

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")

# No `detail`, no `tool`: the structural plugin shape. `plugin_probe_drifts` is
# built at runtime as f"plugin_{name}_drifts", so no branch could ever exist for
# it in any hand-maintained list.
PLUGIN_SOURCE = '''\
def find_probe(root, docs):
    return [{"file": "README.md", "rule": "probe-rule", "expected": "2.0",
             "pos": 0}]


def find_chart(root, docs):
    return [{"file": "Chart.yaml", "rule": "chart-rule", "replicas": 3,
             "pos": 0}]


def find_withdetail(root, docs):
    return [{"file": "README.md", "detail": "probe plugin sentence", "pos": 0}]


def register():
    return {"probe": find_probe, "chart": find_chart,
            "withdetail": find_withdetail}
'''


def _make_repo(root: Path) -> None:
    plugins = root / ".driftcheck_plugins"
    plugins.mkdir(parents=True)
    (plugins / "probe.py").write_text(PLUGIN_SOURCE, encoding="utf-8")

    # Curated detectors that emit structured fields rather than a `detail`:
    # justfile_drifts, python_req_drifts, go_replace_drifts, terraform_lock_drifts.
    (root / "justfile").write_text("@version python@3.12\n", encoding="utf-8")
    (root / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\ndependencies = []\n',
        encoding="utf-8",
    )
    # python_version_drifts: the payload carries `version_file`, which is one of
    # the 32 fields the six-name list could not reach.
    (root / ".python-version").write_text("3.12\n", encoding="utf-8")
    (root / "go.mod").write_text(
        "module example.com/fixture\n\ngo 1.21\n\nrequire github.com/pkg/errors v0.9.1\n",
        encoding="utf-8",
    )
    (root / "go.sum").write_text(
        "github.com/other/thing v1.2.3 h1:aaaa=\n"
        "github.com/other/thing v1.2.3/go.mod h1:bbbb=\n",
        encoding="utf-8",
    )
    (root / "versions.tf").write_text(
        'aws = { source = "hashicorp/aws", version = ">= 5.0.0" }\n', encoding="utf-8"
    )
    (root / ".terraform.lock.hcl").write_text(
        'provider "registry.terraform.io/hashicorp/aws" {\n  version = "3.0.0"\n}\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Fixture\n\nRequires Python 3.9.\n", encoding="utf-8")
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-Af"], cwd=root, check=True)


def _run(root: Path, flag: str) -> str:
    # Both halves are explicit and both are needed. ``PYTHONIOENCODING`` fixes
    # the child's *emitted* encoding; ``encoding=`` fixes this process's
    # *decode*. They are independent, and a Windows runner's ambient cp1252
    # cannot represent the report's UTF-8 (the emoji and the arrow in
    # "→ should be"). Getting only one wrong is invisible until the other
    # changes -- and the symptom lands nowhere near the cause: the decode
    # error kills subprocess's reader thread, so ``run()`` returns a
    # CompletedProcess whose ``stdout`` was never appended to, i.e. **None**.
    # See tests/test_harness_encoding.py, which pins this failure mode.
    env = {**os.environ, "PYTHONPATH": REPO_SRC, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", flag],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.returncode in (0, 1), f"unexpected exit {proc.returncode}: {proc.stderr}"
    assert proc.stdout is not None, (
        f"--report produced no stdout (rc={proc.returncode}); stderr: {proc.stderr}"
    )
    return proc.stdout


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("report_describe")
    _make_repo(root)
    return root


@pytest.fixture(scope="module")
def report(fixture_repo: Path) -> str:
    return _run(fixture_repo, "--report")


@pytest.fixture(scope="module")
def text_output(fixture_repo: Path) -> str:
    return _run(fixture_repo, "")


def _report_bullets(report: str) -> list[str]:
    return [ln for ln in report.splitlines() if ln.startswith("- `")]


def test_report_emits_at_least_one_finding(fixture_repo: Path) -> None:
    """Guard the measurement: the fixture must actually fire detectors.

    Without this the assertions below would pass vacuously against a fixture
    that silently stopped detecting anything -- which is how a test for a
    rendering bug becomes a test for nothing.
    """
    drifts = json.loads(_run(fixture_repo, "--json"))
    fired = {k: v for k, v in drifts.items() if k.endswith("_drifts") and v}
    assert "plugin_probe_drifts" in fired, f"fixture fired only {sorted(fired)}"
    assert len(fired) >= 6, f"fixture is too small to be meaningful: {sorted(fired)}"


def test_no_report_bullet_is_a_raw_payload_repr(report: str) -> None:
    """The core assertion: no bullet in --report carries a Python repr.

    A rendered payload repr starts with the file field the detectors all emit,
    so it is detectable in the emitted text without knowing which key produced
    it. This is the surface an operator reads in a CI job summary and pastes
    into a PR comment.
    """
    offenders = [
        ln for ln in _report_bullets(report)
        if re.search(r":\s*\{['\"]", ln)
    ]
    assert not offenders, f"--report rendering raw payload reprs: {offenders}"


def test_plugin_finding_is_described_readably(report: str) -> None:
    """The plugin path is structural: no branch can exist for a runtime key.

    Before the fix this bullet was the payload's own repr, so the plugin's
    finding -- detected, gating the build, and reported by --json and --sarif --
    reached the one human-facing surface as a Python dict.
    """
    plugin_bullets = [
        ln for ln in _report_bullets(report)
        if "probe-rule" in ln
    ]
    assert plugin_bullets, f"plugin finding missing from --report; got {_report_bullets(report)}"
    assert not re.search(r":\s*\{['\"]", plugin_bullets[0]), (
        f"plugin finding rendered as a repr: {plugin_bullets[0]}"
    )
    assert "expected=2.0" in plugin_bullets[0], plugin_bullets[0]


def test_curated_finding_without_detail_is_described_readably(report: str) -> None:
    """The curated case matters too: this is not only a plugin problem.

    ``python_version_drifts`` reports ``version_file``, and ``freshness_drifts``
    reports ``pinned_version``/``latest_version``. Neither has a ``detail``, so
    both landed on the repr branch before the fix -- a curated key failing the
    same way a plugin does.
    """
    for marker, finding in (
        ("Python 3.9", "python_version_drifts"),
        ("2.31.0", "freshness_drifts"),
    ):
        bullets = [ln for ln in _report_bullets(report) if marker in ln]
        assert bullets, f"{finding} missing from --report (looked for {marker!r})"
        assert not re.search(r":\s*\{['\"]", bullets[0]), (
            f"{finding} rendered as a repr: {bullets[0]}"
        )


def test_no_report_bullet_states_an_empty_target(report: str) -> None:
    """A mismatch sentence must name the value it says the docs should carry.

    This is the quieter half of the same defect: the sentence is assembled from
    a hand-written list of six ``*_version`` field names, and any other version
    field fell off the end, so the report said ``Python 3.9 → should be`` and
    stopped. The finding is there and its subject is named, so it reads as a
    rendering bug rather than the drift being reported.
    """
    offenders = [ln for ln in _report_bullets(report) if "should be" in ln]
    assert offenders, "fixture produced no mismatch sentence to check"
    empty = [ln for ln in offenders if re.search(r"should be\s*$", ln)]
    assert not empty, f"--report emitted a mismatch with no target: {empty}"


def test_report_and_text_agree_on_the_fallback_rendering(
    report: str, text_output: str
) -> None:
    """A key neither surface hand-formats is described the same way in both.

    Scoped to the fallback on purpose: the report and the text printer have
    always worded their bespoke branches differently. What must not differ is
    the floor -- the rendering for keys no surface special-cases.

    Both markers are plugin keys, which is what makes them a floor case rather
    than a coincidence: a ``plugin_*`` key is born at runtime, so no
    hand-maintained list anywhere can contain it. ``freshness_drifts`` was the
    obvious second marker and is deliberately not used -- ``_print_blocking_
    drifts`` hand-formats it (``cli.py``: the ``requests 2.31.0 -> newer:
    2.34.2 (PyPI)`` line), so comparing it against the report's fallback would
    be measuring a bespoke branch against the floor.
    """
    for marker in ("probe-rule", "chart-rule"):
        in_report = [ln for ln in _report_bullets(report) if marker in ln]
        in_text = [ln for ln in text_output.splitlines() if marker in ln]
        assert in_report and in_text, f"{marker} missing from a surface"
        described = next(
            (
                field
                for field in re.findall(r"[\w]+=[\w.\-]+", in_report[0])
                if field in in_text[0]
            ),
            None,
        )
        assert described is not None, (
            f"--report and text disagree on how to describe {marker}: "
            f"{in_report[0]!r} vs {in_text[0]!r}"
        )


def test_report_still_covers_every_finding_json_reports(fixture_repo: Path, report: str) -> None:
    """Retention: nothing detected may vanish from the report.

    The report walks ``_blocking_drifts`` plus the curated informational set,
    so a runtime key is covered here for the same reason it is in the other
    surfaces: a registry over an open key space cannot be a fixed list.
    """
    drifts = json.loads(_run(fixture_repo, "--json"))
    expected = sum(len(v) for k, v in drifts.items() if k.endswith("_drifts") and v)
    bullets = len(_report_bullets(report))
    # Each finding is one bullet; the summary section also uses "- `name`" for
    # the detector breakdown and top-files lists, so assert the floor rather
    # than exact equality against a bullet count that includes those.
    assert bullets >= expected, (
        f"--json reports {expected} findings but --report emitted {bullets} bullets"
    )
