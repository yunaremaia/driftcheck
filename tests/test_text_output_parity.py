"""The text printer must display exactly the findings the exit-code gate counts.

``cli._blocking_drifts`` (via ``_drift_keys_in``) decides the exit status, and
``cli._print_blocking_drifts`` decides what the operator reads. Before this file
existed those were two different enumerations of the same result:

* the gate walked ``DRIFT_KEYS`` **and then** whatever other ``*_drifts`` keys
  the result carries, because the key space is open (``plugins.py`` builds
  ``f"plugin_{name}_drifts"`` at runtime);
* the printer enumerated 62 keys one ``all_drifts.get(...)`` block at a time, so
  22 curated blocking keys and every runtime plugin key fell off the end.

Measured on a fixture repo before the fix -- 10 blocking findings, exit 1, and
four of them never printed::

    driftcheck: .gitattributes: missing .gitattributes ...   lineending_drifts
    driftcheck: README.md: Python 0.34 → should be 3.11.0     python_version_drifts
    driftcheck: .env: .env missing 1 key(s) ... BAR           env_drifts
    driftcheck: README.md: probe plugin finding               plugin_probe_drifts
    driftcheck: info: ... dependabot                          dependabot_drifts
    __EXIT=1

while ``--json`` carried ``bazel_drifts``, ``env_example_drifts``,
``go_replace_drifts``, ``julia_drifts``, ``justfile_drifts`` alongside the four
above, and ``--csv`` wrote all ten as ``severity=blocking``.

That is the worst outcome this tool can produce: the operator reads a clean
report while the build fails, and nothing in the text says a finding exists.

The fix is a generic fallback at the end of ``_print_blocking_drifts``: any
blocking key with no hand-written formatter is rendered generically. The
hand-written blocks are now a formatting preference, never a gate.

Two tests, because the two defects are different in kind:

1. ``test_every_blocking_key_is_printed`` -- registry-driven and exhaustive. It
   feeds one finding for **every** key in ``DRIFT_KEYS`` and requires each
   blocking key to appear in the printer's output. It is exhaustive because it
   enumerates the registry, so the next detector added to ``config.py`` is
   covered without touching this file.
2. the ``test_text_output_shows_*`` tests -- real subprocess, real fixture, real
   five-mode diff, which is the only way to see the process exit status.

Neither can be satisfied by a reading of the source: the first asserts on
captured stdout, the second on a real process verdict.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.cli import (
    _blocking_drifts,
    _print_blocking_drifts,
    _print_informational,
    _print_report,
)
from driftcheck.config import DRIFT_KEYS, INFORMATIONAL_DRIFT_KEYS

# Every field the printers read, derived from their own source rather than
# guessed: a missing one raises KeyError mid-loop and aborts the whole print
# pass, which would fail the test for a fixture reason instead of a product one.
_PRINTER_FIELDS = (
    "action", "actual_count", "cargo_version", "catalog_version",
    "circleci_image", "cmake_version", "compose_image", "composer_version",
    "csproj_version", "current", "current_commit", "dart_version",
    "deno_json_version", "detail", "doc_count", "doc_image", "doc_registry",
    "doc_version", "dockerfile_image", "dotnet_version", "environment_version",
    "file", "floor_source", "floor_version", "gemfile_version", "gitlab_image",
    "gomod_version", "gradle_version", "helm_image", "image", "indexed_commit",
    "jenkins_version", "k8s_image", "kind", "latest_version", "library", "line",
    "lock_version", "makefile_version", "maven_version", "mix_version", "name",
    "npmrc_registry", "nvmrc_version", "package", "package_version", "path",
    "php_version", "pin_version", "pinned_version", "pipfile_version",
    "provider", "pubspec_version", "pyproject_version", "readme_version",
    "requirements_version", "ruby_version", "runner", "setup_version", "source",
    "suggested", "swift_version", "tag", "taskfile_version", "terraform_version",
    "tool", "tool_versions_version", "toolchain_version", "type", "url",
    "version_file", "yarnrc_version",
)

# Fields the printers branch on and print nothing for an unrecognised value, so
# a synthetic finding needs a realistic sub-kind or the row would be absent for
# a fixture reason rather than a product one.
_KIND_OVERRIDES = {
    "lockfile_drifts": "lockfile_stale",
    "dependabot_drifts": "dependabot_missing",
    "env_drifts": "env_missing_keys",
    "env_example_drifts": "env_missing_keys",
}


def _finding(key: str) -> dict:
    d: dict = {field: key for field in _PRINTER_FIELDS}
    d["kind"] = _KIND_OVERRIDES.get(key, key)
    d["tags"] = [key]
    d["features"] = {key: key}
    return d


def _marker(d: dict) -> str:
    """A string that identifies one finding in rendered output.

    Prefers the detector's own ``detail`` prose; otherwise falls back to the
    tool/version pair a formatter would have to print anyway.
    """
    return d.get("detail") or f"{d.get('tool', '')} {d.get('doc_version', '')}".strip()


def test_every_blocking_key_is_printed(capsys: pytest.CaptureFixture) -> None:
    """Every gated key must reach stdout -- no key, on any path.

    Driven by the registry rather than a hardcoded list, so a detector added to
    ``DRIFT_KEYS`` without a printer block fails here instead of shipping as a
    silent drop.
    """
    result: dict = {key: [_finding(key)] for key in DRIFT_KEYS}
    blocking = _blocking_drifts(result)

    # Guard: the gate must actually be gating, or the loop below proves nothing.
    assert len(blocking) == len(set(DRIFT_KEYS) - set(INFORMATIONAL_DRIFT_KEYS))
    assert len(blocking) > 0

    _print_blocking_drifts({k: v for k, v in result.items()}, result)
    out = capsys.readouterr().out

    invisible = sorted(key for key in blocking if key not in out)
    assert not invisible, (
        f"{len(invisible)} blocking key(s) trip the exit code but print nothing "
        f"in text mode, so a failing build looks clean: {invisible}"
    )


def test_every_informational_key_is_printed(capsys: pytest.CaptureFixture) -> None:
    """Same invariant for the informational printer.

    Informational findings do not fail the build, but they are still findings;
    ``changelog_drifts`` had no printer block at all and so was invisible in the
    one mode a human reads.
    """
    result: dict = {key: [_finding(key)] for key in INFORMATIONAL_DRIFT_KEYS}
    _print_informational(result)
    out = capsys.readouterr().out
    invisible = sorted(key for key in INFORMATIONAL_DRIFT_KEYS if key not in out)
    assert not invisible, (
        f"informational key(s) never printed in text mode: {invisible}"
    )


def test_report_prints_every_blocking_key(capsys: pytest.CaptureFixture) -> None:
    """``_print_report`` must not under-report the gate's verdict either."""
    result: dict = {key: [_finding(key)] for key in DRIFT_KEYS}
    result["plugin_runtime_key_drifts"] = [
        {"file": "README.md", "detail": "runtime key finding"}
    ]
    blocking = _blocking_drifts(result)
    assert blocking, "fixture built no blocking findings; the rest is vacuous"

    _print_report(result)
    out = capsys.readouterr().out
    invisible = sorted(key for key in blocking if key not in out)
    assert not invisible, (
        f"blocking key(s) counted by the gate but absent from --report: {invisible}"
    )


# --------------------------------------------------------------------------
# Real subprocess, real fixture, all five modes.
# --------------------------------------------------------------------------

_PLUGIN = """\
def find_widget_drift(root, docs):
    return [{"file": "README.md", "detail": "widget version mismatch"}]


def register():
    return {"widget": find_widget_drift}
"""

_CONFIG = """\
[driftcheck]
exclude_detectors = ["dependabot", "lockfile", "freshness", "typosquat", "lineending"]
"""

# Builtin keys with no hand-written printer block, each with a finding shape its
# detector really emits. `.gitattributes` would otherwise add a lineending
# finding that masks which keys fired.
_FIXTURE_FILES = {
    "README.md": (
        "Requires Bazel 6.5.0.\n\n"
        "Requires Python 3.11.\n\n"
        "Use rules_python 0.34.0\n\n"
        "DataFrames.jl v1.6\n\n"
        "https://example.com/does-not-exist\n"
    ),
    ".bazelversion": "7.1.0\n",
    "MODULE.bazel": 'bazel_dep(name = "rules_python", version = "0.35.0")\n',
    "justfile": "@version python@3.10\n",
    "Project.toml": '[compat]\nDataFrames = "1.5"\n',
    "go.mod": "module x\n\ngo 1.21\n\nrequire github.com/foo/bar v1.2.3\n",
    "go.sum": "github.com/foo/bar v1.2.4 h1:abc\n",
    ".env.example": "FOO=1\nBAR=2\n",
    ".env": "FOO=1\n",
    ".gitattributes": "* text=auto eol=lf\n",
}


@pytest.fixture
def mixed_repo(tmp_path: Path) -> Path:
    root = tmp_path / "mixed_repo"
    (root / ".driftcheck_plugins").mkdir(parents=True)
    (root / ".driftcheck.toml").write_text(_CONFIG, encoding="utf-8")
    (root / ".driftcheck_plugins" / "widget_plugin.py").write_text(
        _PLUGIN, encoding="utf-8"
    )
    for name, body in _FIXTURE_FILES.items():
        (root / name).write_text(body, encoding="utf-8")
    return root


def _run(root: Path, *flags: str) -> subprocess.CompletedProcess:
    # encoding is explicit because the CLI now guarantees UTF-8 on stdout.
    # text=True alone decodes with the *ambient* locale, which on a Windows
    # runner is cp1252: the reader thread then dies on the arrow's 0x9d byte,
    # the buffer is never appended, and proc.stdout silently becomes None.
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _json_blocking_keys(root: Path) -> set[str]:
    result = json.loads(_run(root, "--json").stdout)
    return {
        key
        for key, value in result.items()
        if key.endswith("_drifts")
        and isinstance(value, list)
        and value
        and key not in INFORMATIONAL_DRIFT_KEYS
    }


def test_mixed_fixture_actually_fires(mixed_repo: Path) -> None:
    """Guard for the fixture: without this row every test below is vacuous."""
    keys = _json_blocking_keys(mixed_repo)
    assert "plugin_widget_drifts" in keys, (
        f"fixture plugin produced no runtime key; remaining tests would pass "
        f"vacuously. keys={sorted(keys)}"
    )
    builtin = keys - {"plugin_widget_drifts"}
    assert len(builtin) >= 3, (
        f"expected several builtin blocking findings so the text printer has "
        f"more than the plugin key to render; got {sorted(builtin)}"
    )


def test_text_output_shows_every_blocking_finding(mixed_repo: Path) -> None:
    """Each blocking finding in --json must be visible in the text output.

    Markers are taken from the findings themselves (``detail`` where the detector
    provides one, else the tool/version pair), so this does not hardcode a
    sentence format the printers are free to change.
    """
    result = json.loads(_run(mixed_repo, "--json").stdout)
    proc = _run(mixed_repo)
    assert proc.returncode == 1, (
        f"fixture should fail the build; exited {proc.returncode}: {proc.stdout[:300]}"
    )
    text = proc.stdout

    markers: list[tuple[str, str]] = []
    for key, drifts in result.items():
        if (
            not key.endswith("_drifts")
            or not isinstance(drifts, list)
            or not drifts
            or key in INFORMATIONAL_DRIFT_KEYS
        ):
            continue
        for d in drifts:
            markers.append((key, _marker(d)))

    assert markers, "fixture produced no blocking findings"
    missing = [(k, m) for k, m in markers if m not in text]
    assert not missing, (
        f"{len(missing)} of {len(markers)} blocking finding(s) trip the exit "
        f"code but are absent from the text output, so the operator sees a "
        f"clean report while the build fails: {missing}"
    )


def test_all_five_modes_report_the_same_finding_set(mixed_repo: Path) -> None:
    """Each mode must carry every blocking finding, checked per-surface.

    ``--csv`` and ``--sarif`` put a finding's fields in separate columns, so
    their marker is the file plus the doc version rather than one contiguous
    string; asserting a substring that no column can ever contain would be a
    test of the wrong thing.
    """
    result = json.loads(_run(mixed_repo, "--json").stdout)
    blocking = [
        (key, d)
        for key, drifts in result.items()
        if key.endswith("_drifts")
        and isinstance(drifts, list)
        and drifts
        and key not in INFORMATIONAL_DRIFT_KEYS
        for d in drifts
    ]
    assert blocking, "fixture produced no blocking findings"

    # Contiguous-string markers for the free-form surfaces.
    prose = {_marker(d) for _, d in blocking}
    # (file, doc_version) pairs for the columnar surfaces.
    pairs = {(d.get("file", ""), d.get("doc_version", "")) for _, d in blocking}
    pairs = {(f, v) for f, v in pairs if f}

    for flag, mode in (("--report", "report"), ("", "text")):
        proc = _run(mixed_repo, *([flag] if flag else []))
        assert proc.returncode == 1, (
            f"mode {mode!r} exited {proc.returncode} while --json reports "
            f"blocking findings"
        )
        absent = sorted(m for m in prose if m not in proc.stdout)
        assert not absent, (
            f"mode {mode!r} is missing {len(absent)} finding(s) the gate "
            f"counts: {absent}"
        )

    # --csv: one row per finding, identified by its file column.
    csv_rows = _run(mixed_repo, "--csv").stdout.splitlines()[1:]
    for f, v in sorted(pairs):
        matching = [row for row in csv_rows if row.startswith(f + ",")]
        assert matching, f"--csv has no row for {f!r} (doc_version {v!r})"
        if v:
            assert any(v in row for row in matching), (
                f"--csv row for {f!r} does not carry doc_version {v!r}"
            )

    # --sarif: one result per finding, located by its artifact URI.
    sarif = json.loads(_run(mixed_repo, "--sarif").stdout)
    results = sarif["runs"][0]["results"]
    assert len(results) == len(blocking), (
        f"--sarif emitted {len(results)} result(s) for {len(blocking)} "
        f"blocking finding(s)"
    )
    uris = {
        r.get("locations", [{}])[0].get("physicalLocation", {})
        .get("artifactLocation", {}).get("uri", "")
        for r in results
    }
    for f, _v in sorted(pairs):
        assert any(f in uri for uri in uris), (
            f"--sarif has no result located at {f!r}; uris={sorted(uris)}"
        )