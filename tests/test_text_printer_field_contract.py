"""A hand-written print block may not read a field its detector never builds.

`_print_blocking_drifts` and `_print_informational` are long chains of
`for d in all_drifts.get("<key>_drifts", []):` blocks, each one printing
hand-written fields. Those blocks index their fields directly -- `d['file']`,
`d['doc_registry']` -- so a block that names a field no detector ever emits
raises `KeyError` *mid-loop*.

That is not a cosmetic failure. `_print_blocking_drifts` is called from `main`
before `_print_informational`, so the exception unwinds straight out of the
text renderer: every key printed after the offending one is lost, all
informational output is lost, and the operator gets a traceback on stderr
instead of a report. The exit code is still 1 and `--json` still lists every
finding, so the machine-readable surfaces look healthy while the one surface a
human reads is destroyed.

Measured 2026-10-04 on driftcheck 0.1.x, over a real fixture whose `.npmrc`
registry disagrees with `package.json` `publishConfig.registry`:

    detectors fired: 8 keys, 11 findings
    text mode:       KeyError: 'doc_registry' at cli.py:1155
    text printed:    4 of 8 blocking keys, 0 of 5 informational findings
    --json:          all 8 keys, no error

Both offending blocks are reachable from ordinary input, not exotic payloads:

* `cli.py:1155` read `d['doc_registry']` for `npmrc_drifts`.
  `find_npmrc_drift` emits `file`, `detail`, `npmrc_registry`,
  `package_json_registry`, `npmrc_setting` -- there is no documented side to
  compare against, so there is no `doc_registry`. The block was also a
  duplicate: `cli.py:1132` already printed the same key from `d['detail']`.
* `cli.py:1074` read `d['tool']`, `d['doc_version']`, `d['taskfile_version']`
  for `taskfile_drifts`, a version-comparison shape. `find_taskfile_drift`
  compares task *names* between two files and emits `file`, `kind`, `detail`,
  `keys` -- it can never produce a version pair.

## Why the existing guard did not catch either

`tests/test_text_output_parity.py` builds its findings synthetically:

    d = {field: key for field in _PRINTER_FIELDS}

where `_PRINTER_FIELDS` is derived from the printers' own source. It therefore
stuffs `doc_registry` and `taskfile_version` into every synthetic finding, which
makes the `KeyError` impossible by construction. The guard proves the printers
can render *a dict containing every field they ask for*; it says nothing about
whether any real detector emits those fields. The end-to-end fixture in that
file has no `.npmrc` and no `Taskfile.yml`, so the two paths are never driven
either. This file closes both gaps: the static guard derives the field contract
from the detector side, and the fixture tests drive the real CLI over real
files.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.cli import _print_blocking_drifts, _print_informational
from driftcheck.config import DRIFT_KEYS, INFORMATIONAL_DRIFT_KEYS

_SRC = Path(__file__).resolve().parents[1] / "src" / "driftcheck"
_DETECTORS = _SRC / "detectors"
_SCANNER = _SRC / "detector.py"


def _module_functions() -> dict[str, ast.FunctionDef]:
    """Every module-level function in the detectors package, by name."""
    found: dict[str, ast.FunctionDef] = {}
    for path in sorted(_DETECTORS.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef):
                found[node.name] = node
    return found


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _key_to_detector() -> dict[str, str]:
    """Map each result key in `scan_repo` to the `find_*` that produces it.

    Two shapes cover every key: a local variable assigned from a `find_*` call
    and then used as the value (`x = find_x_drift(...)` -> `{"x_drifts": x}`),
    and a `find_*` called inline as the value. Keys whose value is neither are
    left out and reported by `test_the_contract_covers_the_registries`, so a
    mapping that silently degrades to nothing cannot pass as full coverage.
    """
    tree = ast.parse(_SCANNER.read_text(encoding="utf-8"))
    scan = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "scan_repo"
    )

    var_to_find: dict[str, str] = {}
    for node in ast.walk(scan):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            name = _call_name(node.value)
            if name and name.startswith("find_"):
                var_to_find[node.targets[0].id] = name

    mapping: dict[str, str] = {}
    for node in ast.walk(scan):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value.endswith("_drifts")
            ):
                continue
            if isinstance(value, ast.Name) and value.id in var_to_find:
                mapping[key.value] = var_to_find[value.id]
            elif isinstance(value, ast.Call):
                name = _call_name(value)
                if name and name.startswith("find_"):
                    mapping[key.value] = name
    return mapping


def _fields_built_by(func_name: str, functions: dict[str, ast.FunctionDef],
                     seen: frozenset[str] = frozenset()) -> set[str]:
    """String keys of every dict literal a function (or its helpers) builds.

    Transitively closed over same-package helper calls: several detectors
    assemble their findings through a `parse_*`/`_extract_*` helper, and a
    field produced there is just as real as one produced inline. Recursion is
    guarded by `seen` because the helper graph contains cycles.
    """
    if func_name in seen:
        return set()
    node = functions.get(func_name)
    if node is None:
        return set()
    seen = seen | {func_name}

    fields: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            for k in child.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    fields.add(k.value)
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id in functions:
                fields |= _fields_built_by(child.func.id, functions, seen)
    return fields


def _blocks_by_key(function) -> dict[str, set[str]]:
    """Fields each `for d in all_drifts.get("<key>_drifts", [])` block indexes.

    Read from the printers' own AST rather than by regex over the whole body,
    so a field named in a *different* block is never credited to this one.
    """
    src = inspect.getsource(function)
    blocks: dict[str, set[str]] = {}
    tree = ast.parse(src.lstrip())
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Call):
            continue
        if not isinstance(node.iter.func, ast.Attribute):
            continue
        if node.iter.func.attr != "get" or not node.iter.args:
            continue
        first = node.iter.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            continue
        if not first.value.endswith("_drifts"):
            continue
        fields: set[str] = set()
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
                    if isinstance(sub.value, ast.Name) and sub.value.id == "d":
                        fields.add(str(sub.slice.value))
        if fields:
            blocks.setdefault(first.value, set()).update(fields)
    return blocks


FUNCTIONS = _module_functions()
KEY_TO_DETECTOR = _key_to_detector()
BLOCKING_BLOCKS = _blocks_by_key(_print_blocking_drifts)
INFORMATIONAL_BLOCKS = _blocks_by_key(_print_informational)
ALL_BLOCKS = {**BLOCKING_BLOCKS, **INFORMATIONAL_BLOCKS}


def test_the_contract_covers_the_registries() -> None:
    """Guard against the analysis silently degenerating to nothing.

    A field-contract guard derived from the wrong side proves nothing: this is
    the same failure mode as deriving a detector's key set from the renderer,
    where the renderer and the detector are the same source and the check
    cannot fail. Pin the size of every derived set.
    """
    assert len(FUNCTIONS) > 150, f"parsed only {len(FUNCTIONS)} detector functions"
    assert len(KEY_TO_DETECTOR) >= 70, (
        f"bound only {len(KEY_TO_DETECTOR)} of {len(DRIFT_KEYS)} drift keys to a "
        "detector function; the field-contract check would silently skip them"
    )
    assert len(ALL_BLOCKS) >= 60, f"parsed only {len(ALL_BLOCKS)} hand-written print blocks"


def test_hand_blocks_only_read_fields_their_detector_builds() -> None:
    """The contract: every field a print block indexes must exist on arrival.

    One violation aborts the whole text render, so this asserts over all
    blocks rather than per-key -- a key-by-key test that swallowed the
    exception would report green.
    """
    violations: list[tuple[str, str, list[str]]] = []
    for key, required in sorted(ALL_BLOCKS.items()):
        detector = KEY_TO_DETECTOR.get(key)
        if detector is None:
            # No statically identifiable producer (built by a loop or merged in
            # at runtime). The end-to-end tests below cover what the static
            # pass cannot; skipping here is deliberate, not a hole in the fix.
            continue
        produced = _fields_built_by(detector, FUNCTIONS)
        missing = sorted(required - produced)
        if missing:
            violations.append((key, detector, missing))

    assert not violations, (
        f"{len(violations)} hand-written print block(s) index fields their "
        "detector never emits, so the text renderer raises KeyError mid-loop "
        "and every finding printed after it -- plus all informational output "
        "-- is lost, while the exit code stays 1 and --json stays complete: "
        + "; ".join(
            f"{key} (from {detector}) indexes {missing}" for key, detector, missing in violations
        )
    )


def test_informational_keys_are_not_hand_formatted_by_the_blocking_printer() -> None:
    """A key cannot be formatted by both printers, or it prints twice.

    `freshness_drifts` is in `INFORMATIONAL_DRIFT_KEYS`, so the blocking
    printer must leave it to the informational one. It had a hand block in
    `_print_blocking_drifts` *and* no hand block in `_print_informational`, so
    every finding printed twice -- once formatted as a blocking finding with no
    `info:` marker, once as informational -- and an operator could not tell
    which lines fail the build.
    """
    both = sorted(set(BLOCKING_BLOCKS) & INFORMATIONAL_DRIFT_KEYS)
    assert not both, (
        "informational key(s) have a hand-written block in the blocking "
        "printer as well, so each finding is printed twice, once with no "
        f"`info:` marker and once with one: {both}"
    )


# --- end-to-end: the real CLI over real files --------------------------

NPMRC_FIXTURE = {
    "README.md": "# demo\n\nRequires Node 20.11.0.\n",
    "package.json": (
        "{\n"
        '  "name": "demo",\n'
        '  "version": "1.0.0",\n'
        '  "engines": {"node": ">=20"},\n'
        '  "publishConfig": {"registry": "https://registry.example.com/"}\n'
        "}\n"
    ),
    ".npmrc": "registry=https://registry.npmjs.org/\n",
    ".gitattributes": "* text=auto eol=lf\n",
}

TASKFILE_FIXTURE = {
    "README.md": "# demo\n",
    "Taskfile.yml": "build:\n    @echo build\ntest:\n    @echo test\n",
    "Makefile": "clean:\n    rm -rf build\n",
    ".gitattributes": "* text=auto eol=lf\n",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _run(root: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "driftcheck", str(root), *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _blocking_findings(root: Path) -> list[tuple[str, dict]]:
    result = json.loads(_run(root, "--json").stdout)
    return [
        (key, d)
        for key, drifts in result.items()
        if key.endswith("_drifts")
        and isinstance(drifts, list)
        and drifts
        and key not in INFORMATIONAL_DRIFT_KEYS
        for d in drifts
        if isinstance(d, dict)
    ]


def _marker(d: dict) -> str:
    """A string identifying one finding in rendered output.

    Prefers the detector's own prose so this does not hardcode a sentence the
    printers are free to reword.
    """
    return d.get("detail") or f"{d.get('tool', '')} {d.get('doc_version', '')}".strip()


@pytest.mark.parametrize(
    ("name", "files", "expected_key"),
    [
        ("npmrc", NPMRC_FIXTURE, "npmrc_drifts"),
        ("taskfile", TASKFILE_FIXTURE, "taskfile_drifts"),
    ],
)
def test_text_mode_reports_the_finding_it_gates(
    tmp_path: Path, name: str, files: dict[str, str], expected_key: str
) -> None:
    """The finding must appear in text mode, and text mode must not crash.

    `--json` is the control: it runs the same detectors and must contain the
    key. Without it this test could pass on a fixture that simply never fired.
    """
    root = _write(tmp_path / name, files)

    findings = _blocking_findings(root)
    keys = {key for key, _ in findings}
    assert expected_key in keys, (
        f"fixture did not fire {expected_key}; the rest of this test would be "
        f"vacuous. fired={sorted(keys)}"
    )

    proc = _run(root)
    assert proc.returncode == 1, (
        f"fixture should fail the build; exited {proc.returncode}: {proc.stdout[:300]}"
    )
    assert "Traceback" not in proc.stderr, (
        "the text renderer crashed, so every finding printed after the offending "
        f"block is lost and the operator gets a traceback instead of a report:\n"
        f"{proc.stderr[-1500:]}"
    )

    expected = [d for key, d in findings if key == expected_key]
    missing = [d for d in expected if _marker(d) not in proc.stdout]
    assert not missing, (
        f"{expected_key} trips the exit code and appears in --json but is absent "
        f"from the text output: {[ _marker(d) for d in missing ]}"
    )
