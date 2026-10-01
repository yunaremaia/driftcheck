"""Regression test: the reusable driftcheck workflow must not interpolate
caller-supplied inputs into its `run:` script bodies.

`zizmor` flags every `${{ inputs.* }}` expansion inside a `run:` block as
`template-injection`: the Actions runner substitutes the expression *before*
bash parses the line, so surrounding quotes cannot stop a caller from injecting
shell syntax. This test executes the workflow's own `run:` blocks with hostile
input values and asserts nothing gets executed and each value stays a single
argv entry.
"""

import os
import re
import shutil
import subprocess
import sys
import textwrap

import pytest

WORKFLOW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".github",
    "workflows",
    "driftcheck.yml",
)

# These tests execute the workflow's bash steps locally. Windows runners have
# no POSIX bash by default (git-bash is not on PATH in CI), so skip there
# instead of failing — the workflow itself only ever runs on ubuntu-latest.
requires_bash = pytest.mark.skipif(
    sys.platform.startswith("win") or not shutil.which("bash"),
    reason="needs a POSIX bash; the workflow runs on ubuntu-latest",
)

# `mapfile` needs bash 4+; macOS still ships 3.2. The workflow must stay
# parseable there, so the test suite guards against that regression.
BASH4_ONLY = re.compile(
    r"\bmapfile\b|\breadarray\b|\$\{[A-Za-z_]+,,\}|\$\{[A-Za-z_]+\^\^\}|declare -A"
)


BLOCK_RE = re.compile(
    r"      - name: (Build driftcheck args|Run driftcheck)\n(?:.*\n)*?"
    r"        run: \|\n((?:          .*\n|\n)+)"
)


def _step_scripts():
    with open(WORKFLOW, encoding="utf-8") as fh:
        blocks = BLOCK_RE.findall(fh.read())
    assert len(blocks) == 2, f"expected 2 run blocks, found {[b[0] for b in blocks]}"
    # strip the 10-space YAML block indent
    return [
        textwrap.dedent("\n".join(line[10:] for line in body.rstrip("\n").split("\n")))
        for _, body in blocks
    ]


def test_workflow_steps_avoid_bash4_only_builtins():
    """The workflow must stay runnable under bash 3.2 (macOS default).

    `mapfile`/`readarray` need bash 4+; using them here broke the CI matrix on
    macOS while passing locally on bash 5. Comments are excluded so prose may
    still name the builtins it avoids.
    """
    offenders = []
    for idx, script in enumerate(_step_scripts()):
        code = "\n".join(
            line for line in script.split("\n") if not line.lstrip().startswith("#")
        )
        for match in BASH4_ONLY.finditer(code):
            offenders.append(f"step {idx}: {match.group(0)}")
    assert not offenders, "bash 4+ only construct in workflow: " + "; ".join(offenders)


def test_workflow_has_no_template_injection_in_run_blocks():
    """zizmor-equivalent check: no input expression may appear inside run:."""
    with open(WORKFLOW, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    in_run = False
    offenders = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("run:"):
            in_run = True
            continue
        if in_run:
            if stripped and not line.startswith("          "):
                in_run = False
                continue
            if "inputs." in stripped:
                offenders.append(f"{lineno}: {stripped}")
    assert not offenders, "input expressions inside run: -> " + "; ".join(offenders)


@requires_bash
@pytest.mark.parametrize(
    "label,payload_template",
    [
        ("semicolon", "x; touch {pwned}; echo INJECTED"),
        ("command-substitution", "x$(touch {pwned})y"),
        ("backtick", "x`touch {pwned}`y"),
        ("pipe", "x | touch {pwned}"),
        ("newline", "x\ntouch {pwned}"),
    ],
)
def test_hostile_input_is_not_executed(tmp_path, label, payload_template):
    """Run both steps locally with a hostile input; assert no command executes
    and the payload arrives as exactly one argv entry."""
    build, run = _step_scripts()

    pwned = tmp_path / "PWNED"
    payload = payload_template.format(pwned=pwned)

    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "driftcheck"
    stub.write_text(
        '#!/bin/bash\nfor a in "$@"; do echo "ARGV<<$a>>"; done\nexit 0\n'
    )
    stub.chmod(0o755)

    github_output = tmp_path / "github_output"
    github_output.write_text("")

    env = dict(os.environ)
    env.update(
        {
            "INPUT_DETECTORS": payload,
            "INPUT_EXCLUDE": "",
            "INPUT_FAIL_ON_INFORMATIONAL": "false",
            "INPUT_OUTPUT_FORMAT": "text",
            "INPUT_SARIF_UPLOAD": "false",
            "INPUT_PATH": ".",
            "INPUT_FAIL_ON_DRIFT": "false",
            "GITHUB_OUTPUT": str(github_output),
            "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        }
    )

    first = subprocess.run(
        ["bash", "-c", build], env=env, capture_output=True, text=True
    )
    assert first.returncode == 0, first.stderr

    env["DRIFTCHECK_ARGS"] = github_output.read_text().rstrip("\n")
    second = subprocess.run(
        ["bash", "-c", run], env=env, capture_output=True, text=True
    )

    assert not pwned.exists(), f"{label}: injected command executed"

    argv = re.findall(r"ARGV<<(.*?)>>", second.stdout, re.S)
    carrying = [a for a in argv if "touch" in a or "PWNED" in a or a.startswith("x")]
    assert len(carrying) == 1, f"{label}: payload spread over {len(carrying)} argv entries: {argv}"


@requires_bash
def test_build_step_emits_valid_heredoc(tmp_path):
    """The args heredoc must round-trip: one flag per line between the markers."""
    build, run = _step_scripts()

    github_output = tmp_path / "github_output"
    github_output.write_text("")
    env = dict(os.environ)
    env.update(
        {
            "INPUT_DETECTORS": "rust-cargo,node",
            "INPUT_EXCLUDE": "bun",
            "INPUT_FAIL_ON_INFORMATIONAL": "false",
            "INPUT_OUTPUT_FORMAT": "sarif",
            "INPUT_SARIF_UPLOAD": "false",
            "GITHUB_OUTPUT": str(github_output),
        }
    )
    assert subprocess.run(["bash", "-c", build], env=env).returncode == 0

    lines = github_output.read_text().split("\n")
    assert lines[0] == "driftcheck_args<<DRIFTCHECK_ARGS_EOF"
    assert lines[-1] == ""
    assert lines[-2] == "DRIFTCHECK_ARGS_EOF"

    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "driftcheck"
    stub.write_text(
        '#!/bin/bash\nfor a in "$@"; do echo "ARGV<<$a>>"; done\nexit 0\n'
    )
    stub.chmod(0o755)

    env.update(
        {
            "DRIFTCHECK_ARGS": github_output.read_text().rstrip("\n"),
            "INPUT_PATH": ".",
            "INPUT_FAIL_ON_DRIFT": "false",
            "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        }
    )
    out = subprocess.run(
        ["bash", "-c", run], env=env, capture_output=True, text=True
    ).stdout
    argv = re.findall(r"ARGV<<(.*?)>>", out, re.S)
    assert argv == [
        ".",
        "--only",
        "rust-cargo,node",
        "--exclude",
        "bun",
        "--no-informational",
        "--sarif",
    ], argv
