"""Tests for driftcheck --explain command (issue #271)."""
from pathlib import Path
import json
import sys
import pytest
from driftcheck.explain import Explainer


def test_explain_returns_full_context(tmp_path):
    """Explain should return drift type, file, line, actual, expected, diff, impact, fix."""
    # Create a fake repo with README that has a stale Rust version
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# My Project\n\nRequires Rust 1.93.0 or later.\n")

    explainer = Explainer(tmp_path)
    drift = {
        "file": "README.md",
        "doc_version": "1.93.0",
        "toolchain_version": "1.96.1",
    }
    result = explainer.explain(drift, "rust_drifts")

    assert result["drift"] == "rust_drifts"
    assert result["file"] == "README.md"
    assert result["line"] == 3  # line with "1.93.0"
    assert result["actual"] == "1.93.0"
    assert result["expected"] == "1.96.1"
    assert "- 1.93.0" in result["diff"]
    assert "+ 1.96.1" in result["diff"]
    assert "Rust" in result["impact"] or "compile" in result["impact"]
    assert "1.93.0" in result["fix"]
    assert "1.96.1" in result["fix"]


def test_explain_text_format(tmp_path):
    """explain_text should return human-readable multi-line string."""
    (tmp_path / "README.md").write_text("# Project\n\nNode 18.0.0\n")

    explainer = Explainer(tmp_path)
    drift = {
        "file": "README.md",
        "doc_version": "18.0.0",
        "package_version": "20.0.0",
    }
    text = explainer.explain_text(drift, "node_drifts")

    assert "Drift: node_drifts" in text
    assert "File: README.md" in text
    assert "Actual: 18.0.0" in text
    assert "Expected: 20.0.0" in text


def test_explain_json_format(tmp_path):
    """explain_json should return a dict (JSON-serializable)."""
    (tmp_path / "README.md").write_text("# Project\n\nGo 1.20\n")

    explainer = Explainer(tmp_path)
    drift = {
        "file": "README.md",
        "doc_version": "1.20",
        "gomod_version": "1.22",
    }
    result = explainer.explain_json(drift, "go_drifts")

    assert isinstance(result, dict)
    assert result["drift"] == "go_drifts"
    assert result["file"] == "README.md"
    assert result["actual"] == "1.20"
    assert result["expected"] == "1.22"


def test_explain_all_gathers_all_drifts(tmp_path):
    """explain_all should explain every drift in scan results."""
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\nNode 18.0.0\n")

    explainer = Explainer(tmp_path)
    results = {
        "rust_drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1"}],
        "node_drifts": [{"file": "README.md", "doc_version": "18.0.0", "package_version": "20.0.0"}],
    }
    all_exp = explainer.explain_all(results)

    assert len(all_exp) == 2
    types = {e["drift"] for e in all_exp}
    assert types == {"rust_drifts", "node_drifts"}


def test_explain_fix_updates_file(tmp_path):
    """explain_fix should update docs file (not toolchain files)."""
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    explainer = Explainer(tmp_path)
    drift = {
        "file": "README.md",
        "doc_version": "1.93.0",
        "toolchain_version": "1.96.1",
    }
    result = explainer.explain_fix(drift, "rust_drifts")

    assert result == "README.md"
    content = (tmp_path / "README.md").read_text()
    assert "1.96.1" in content
    assert "1.93.0" not in content


def test_explain_fix_skips_toolchain_files(tmp_path):
    """explain_fix should NOT modify toolchain/manifest files."""
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    explainer = Explainer(tmp_path)
    drift = {
        "file": "rust-toolchain.toml",
        "doc_version": "1.96.1",
    }
    result = explainer.explain_fix(drift, "rust_drifts")

    assert result is None


def test_explain_fix_missing_file(tmp_path):
    """explain_fix returns None when file doesn't exist."""
    explainer = Explainer(tmp_path)
    drift = {
        "file": "NONEXISTENT.md",
        "doc_version": "1.0",
    }
    result = explainer.explain_fix(drift, "rust_drifts")
    assert result is None


def test_explain_impact_description_for_known_drift_types():
    """Each drift type should have a meaningful impact description."""
    from driftcheck.explain import IMPACT_DESCRIPTIONS

    assert "rust_drifts" in IMPACT_DESCRIPTIONS
    assert "node_drifts" in IMPACT_DESCRIPTIONS
    assert "python_drifts" in IMPACT_DESCRIPTIONS
    assert "go_drifts" in IMPACT_DESCRIPTIONS
    # Impact should not be empty
    for key, desc in IMPACT_DESCRIPTIONS.items():
        assert len(desc) > 20, f"Impact description for {key} is too short: {desc!r}"


def test_cli_explain_flag(tmp_path, monkeypatch):
    """CLI --explain should print explanation for a drift."""
    # Create test repo
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    from driftcheck.cli import main

    monkeypatch.chdir(tmp_path)
    exit_code = main(["--explain", "rust_drifts:README.md", "--explain-format", "text"])
    assert exit_code == 0


def test_cli_explain_all(tmp_path, monkeypatch):
    """CLI --explain-all should print all drifts."""
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    from driftcheck.cli import main

    monkeypatch.chdir(tmp_path)
    exit_code = main(["--explain-all"])
    assert exit_code == 0


def test_cli_explain_json_format(tmp_path, monkeypatch, capsys):
    """CLI --explain --explain-format json should output valid JSON."""
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    from driftcheck.cli import main

    monkeypatch.chdir(tmp_path)
    exit_code = main(["--explain", "rust_drifts:README.md", "--explain-format", "json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["drift"] == "rust_drifts"
    assert data["actual"] == "1.93.0"
    assert data["expected"] == "1.96.1"


def test_cli_explain_fix(tmp_path, monkeypatch, capsys):
    """CLI --explain --explain-fix should apply the fix."""
    (tmp_path / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.96.1"\n')
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")

    from driftcheck.cli import main

    monkeypatch.chdir(tmp_path)
    exit_code = main(["--explain", "rust_drifts:README.md", "--explain-fix"])
    assert exit_code == 0

    content = (tmp_path / "README.md").read_text()
    assert "1.96.1" in content


# --- explain: both halves for findings that name no documented field ---
#
# The payloads below are verbatim from `--json` output of real scans. Before
# `describe_pair` existed these findings rendered "Actual: " with nothing after
# it, an empty "Expected", an empty diff, and a fix of "Cannot determine fix",
# while the same finding printed its real values in the scan -- which is the
# user-visible defect this pins.


def test_explain_renders_both_values_for_a_finding_with_no_documented_field(tmp_path):
    """A real actions finding is explained with both halves filled in.

    Real ``actions_drifts`` payload shape (``a2a-drift/.github/workflows/ci.yml``):
    no ``doc_*`` field anywhere, which is 301 of 330 measured findings.
    """
    workflow = "name: CI\n\njobs:\n  build:\n    steps:\n      - uses: actions/checkout@v4\n"
    (tmp_path / "ci.yml").write_text(workflow)
    drift = {"file": "ci.yml", "action": "actions/checkout", "current": "v4",
             "suggested": "v5", "pos": workflow.index("actions/checkout")}

    result = Explainer(tmp_path).explain(drift, "actions_drifts")

    assert result["actual"] == "v4"
    assert result["expected"] == "v5"
    assert result["diff"] == "- v4\n+ v5"
    assert "actions/checkout" not in result["diff"]
    assert result["line"] == 6
    assert "replace 'v4' with 'v5'" in result["fix"]


def test_explain_text_shows_the_pair_for_a_no_documented_field_finding(tmp_path):
    """The text surface prints the same two values the scan printed."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nhttpx = "^0.27"\n')
    drift = {"file": "pyproject.toml", "package": "httpx", "pinned_version": "0.27",
             "latest_version": "0.28.1", "pos": 0}

    text = Explainer(tmp_path).explain_text(drift, "freshness_drifts")

    assert "Actual: 0.27" in text
    assert "Expected: 0.28.1" in text
    assert "httpx" not in text.split("Fix:")[0].split("Diff:")[1]


def test_a_condition_finding_is_fixed_by_its_own_sentence_not_by_a_refusal(tmp_path):
    """A finding with no pair reports its own condition as the fix.

    Real ``lockfile_missing`` payload from ``a2a-drift``: ``poetry.lock`` is
    absent, so there is no value to substitute and no fix this function can
    apply. Saying "Cannot determine fix" about a finding that carries its own
    explanation is the wrong answer -- the sentence is the fix.
    """
    (tmp_path / "poetry.lock").write_text("")
    drift = {"file": "poetry.lock", "kind": "lockfile_missing",
             "detail": "missing poetry.lock \u2014 pyproject.toml exists but no "
                       "lockfile found (run package manager install)", "pos": 0}

    result = Explainer(tmp_path).explain(drift, "lockfile_drifts")

    assert "Cannot determine fix" not in result["fix"]
    assert result["fix"] == result["fix"].strip()
    assert "missing poetry.lock" in result["fix"]
    assert result["actual"] == ""
    assert result["diff"] == ""


def test_find_line_uses_a_recorded_offset_rather_than_searching_for_the_value(tmp_path):
    """A detector's recorded offset is the exact line, even when it is not the first.

    Many detectors record ``m.start()``, so the offset of the value the finding
    is about -- not the first line that merely mentions it.
    """
    content = "# Project\n\nNode 18.0.0\n\n## Other\n\nNode 18.0.0\n"
    (tmp_path / "README.md").write_text(content)
    explainer = Explainer(tmp_path)

    first = content.index("18.0.0")
    second = content.index("18.0.0", first + 1)
    assert explainer._find_line("README.md", "18.0.0", second) == 7
    assert explainer._find_line("README.md", "18.0.0", first) == 3


def test_find_line_falls_back_to_searching_when_pos_is_not_tracked(tmp_path):
    """A literal ``0`` means "offset not tracked", so the search still runs.

    Measured over the real corpus, 92 findings carry ``pos=0`` (lockfiles,
    typosquat and freshness detectors record no offset) and 175 carry a real one.
    A falsy offset is indistinguishable from a real offset of zero, so it must
    not be taken as "line 1" or as "no line".
    """
    (tmp_path / "README.md").write_text("# Project\n\nRust 1.93.0\n")
    explainer = Explainer(tmp_path)

    assert explainer._find_line("README.md", "1.93.0", 0) == 3
    assert explainer._find_line("README.md", "1.93.0", None) == 3
    assert explainer._find_line("README.md", "absent", 0) is None


def test_explain_fix_declines_a_finding_with_no_pair(tmp_path):
    """No pair means no substitution, so the file is left untouched.

    Real ``lineending_drifts`` payload from ``a2a-drift``: a missing
    ``.gitattributes`` is a condition with a sentence, not two disagreeing
    values. There is nothing to splice, so the file must come back unchanged
    rather than have a value written into it.
    """
    original = "lineending = lf\n"
    (tmp_path / ".gitattributes").write_text(original)
    drift = {"file": ".gitattributes", "kind": "lineending",
             "detail": "missing .gitattributes with `* text=auto eol=lf`"}

    result = Explainer(tmp_path).explain_fix(drift, "lineending_drifts")

    assert result is None
    assert (tmp_path / ".gitattributes").read_text() == original
