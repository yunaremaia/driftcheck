"""A hand-written print block may not read a field its detector never emits.

## The class

`_print_blocking_drifts` / `_print_informational` are long chains of
`for d in all_drifts.get("<key>_drifts", []):` blocks that index their fields
directly (`d['detail']`). One field the detector cannot build raises `KeyError`
*mid-loop*, inside `main`, before the informational printer runs. Every
blocking finding printed after the offending block is lost, every informational
finding is lost, and the operator gets a traceback instead of a report — while
the exit code stays 1 and `--json` lists everything, so the machine-readable
surfaces look healthy and the one a human reads is destroyed.

## Why the existing guard did not catch these

`tests/test_text_printer_field_contract.py::_fields_built_by` returns the
**union** of the keys of every dict literal a detector builds. A detector that
emits *two shapes* under one drift key passes that check and then raises at
runtime on whichever shape lacks the field: the union is satisfied by the other
branch's literal, but a real finding only ever has one shape.

Measured 2026-10-04 on driftcheck 0.1.51, two live instances, both reachable
from ordinary input:

    $ driftcheck <repo> --only docker-multistage
    KeyError: 'detail' at cli.py:1039
    $ driftcheck <repo> --only python-version
    KeyError: 'version_file' at cli.py:1157

* `find_dockerfile_multistage_drift` appends `{file, detail, image, tags}` for
  conflicting stage tags, but `{file, doc_image, dockerfile_image, pos}` when
  the docs name a different tag for the final stage. The block reads
  `d['detail']`, so the second shape aborts the render.
* `find_python_version_drift` appends `version_file` for its `.python-version`
  and doc shapes, but the GitHub Actions `setup-python` shape carries
  `workflow_version` instead. The block reads `d['version_file']`, so that
  shape aborts the render.

This file closes the gap by checking the contract **per emit site** — each
dict literal the detector can append must independently satisfy the block —
plus two end-to-end tests that drive the real CLI over real files.

`tests/test_text_printer_field_contract.py` keeps the union check and its
end-to-end fixtures; it is the union that is too weak, not the file.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from driftcheck.cli import _print_blocking_drifts, _print_informational

_SRC = Path(__file__).resolve().parents[1] / "src" / "driftcheck"
_DETECTORS = _SRC / "detectors"
_SCANNER = _SRC / "detector.py"


def _functions() -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for path in sorted(_DETECTORS.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef):
                out[node.name] = node
    return out


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _key_to_detector() -> dict[str, str]:
    """Map each `scan_repo` result key to the `find_*` that produces it."""
    tree = ast.parse(_SCANNER.read_text(encoding="utf-8"))
    scan = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "scan_repo")

    var_to_find: dict[str, str] = {}
    for node in ast.walk(scan):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)):
            name = _call_name(node.value)
            if name and name.startswith("find_"):
                var_to_find[node.targets[0].id] = name

    mapping: dict[str, str] = {}
    for node in ast.walk(scan):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and key.value.endswith("_drifts")):
                continue
            if isinstance(value, ast.Name) and value.id in var_to_find:
                mapping[key.value] = var_to_find[value.id]
            elif isinstance(value, ast.Call):
                name = _call_name(value)
                if name and name.startswith("find_"):
                    mapping[key.value] = name
    return mapping


# Marks a payload field whose value is computed rather than literal, so a
# branch test on it cannot be evaluated from the AST alone.
UNKNOWN = object()


def _shape(node: ast.Dict) -> dict:
    """One emit site's payload: field name -> literal value, or UNKNOWN.

    Values are carried as well as names because a print block branches on one
    (`d.get("type") == "python_requires"`): whether a field is required depends
    on what the shape *says*, not only on which fields it has.
    """
    out: dict = {}
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            out[k.value] = v.value if isinstance(v, ast.Constant) else UNKNOWN
    return out


def _finding_literals(func_name: str, functions: dict[str, ast.FunctionDef],
                      seen: frozenset[str] = frozenset()) -> list[dict]:
    """The payload of each dict literal that becomes a finding.

    One entry per emit site, not one union per function: two shapes under one
    drift key are two findings, and only the union hides the mismatch.

    A literal counts as a finding when it is appended to / returned as the
    accumulating `drifts` list, so a parser's intermediate dict (`{image, tag,
    line}` from a `parse_*` helper) is not mistaken for a payload a printer
    will ever see. Transitive over same-package helper calls, guarded by `seen`
    because the helper graph contains cycles.
    """
    if func_name in seen:
        return []
    node = functions.get(func_name)
    if node is None:
        return []
    seen = seen | {func_name}

    out: list[dict] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = child.func.value if isinstance(child.func, ast.Attribute) else None
        appends_to_list = (
            isinstance(child.func, ast.Attribute)
            and child.func.attr in ("append", "extend")
            and isinstance(target, ast.Name) and "drift" in target.id
        )
        returns_findings = (
            isinstance(child.func, ast.Name)
            and bool(child.args)
            and isinstance(child.args[0], ast.List)
        )
        if appends_to_list or returns_findings:
            elements = child.args if appends_to_list else child.args[0].elts  # type: ignore[attr-defined]
            for elt in elements:
                for sub in ast.walk(elt):
                    if isinstance(sub, ast.Dict):
                        out.append(_shape(sub))
        if isinstance(child.func, ast.Name) and child.func.id in functions:
            out.extend(_finding_literals(child.func.id, functions, seen))
    return out


def _blocks_by_key(function) -> dict[str, set[str]]:
    """Fields each `for d in all_drifts.get("<key>_drifts", [])` block reads.

    A read inside an `if` is exempt. `docker_bases` branches on `'tags' in d`,
    `python_setup` on `d.get("type")`, `lockfile` on `d.get("kind")`: the
    branch *is* the author's assertion that the fields under it are
    conditional, and a finding that lacks them takes the other arm. Tracking
    which arm a given shape takes means evaluating the branch condition per
    field — and an `elif` chain composes as a disjunction of arms, so getting
    that wrong reports correct code as broken, which teaches the reader to
    ignore the check. Exempting branch reads keeps the check's verdict equal
    to "unguarded read of a field no shape carries", which is the defect.

    A read that is unconditional is required of *every* shape the detector
    emits, so the check is per emit site rather than per detector.
    """
    import inspect

    blocks: dict[str, set[str]] = {}
    tree = ast.parse(inspect.getsource(function).lstrip())
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
        for stmt in node.body:
            if isinstance(stmt, ast.If):
                continue  # conditional reads are the author's, not a contract
            for sub in ast.walk(stmt):
                if (isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant)
                        and isinstance(sub.value, ast.Name) and sub.value.id == "d"):
                    blocks.setdefault(first.value, set()).add(str(sub.slice.value))
    return {k: v for k, v in blocks.items() if v}


FUNCTIONS = _functions()
KEY_TO_DETECTOR = _key_to_detector()
ALL_BLOCKS = {
    **_blocks_by_key(_print_blocking_drifts),
    **_blocks_by_key(_print_informational),
}


def test_the_per_emit_site_analysis_is_not_vacuous() -> None:
    """Guard the analysis itself: a contract derived wrong proves nothing.

    Same failure mode the existing union guard has to guard against — if the
    emit-site extraction finds nothing, every check below passes silently.
    """
    assert len(FUNCTIONS) > 150, f"parsed only {len(FUNCTIONS)} detector functions"
    assert len(KEY_TO_DETECTOR) >= 70, (
        f"bound only {len(KEY_TO_DETECTOR)} drift keys to a detector; the "
        "per-emit-site check would silently skip the rest"
    )
    assert len(ALL_BLOCKS) >= 60, f"parsed only {len(ALL_BLOCKS)} print blocks"

    total = sum(len(_finding_literals(det, FUNCTIONS))
                for det in set(KEY_TO_DETECTOR.values()))
    assert total >= 120, (
        f"found only {total} finding literals across the detector package; the "
        "per-emit-site check has too little to inspect"
    )


def test_every_finding_shape_satisfies_its_print_block() -> None:
    """The contract: every shape a detector emits carries every field read.

    Checked per emit site because a detector that emits two shapes under one
    drift key satisfies a union check with the fields of the *other* shape and
    then raises `KeyError` on the one that lacks them. One such violation
    aborts the whole text render, so this asserts over all blocks rather than
    per-key: a key-by-key test that swallowed the error would report green.
    """
    violations: list[str] = []
    for key, required in sorted(ALL_BLOCKS.items()):
        detector = KEY_TO_DETECTOR.get(key)
        if detector is None:
            # Built by a loop or merged in at runtime (plugin detectors); the
            # end-to-end tests below cover what the static pass cannot.
            continue
        for i, shape in enumerate(_finding_literals(detector, FUNCTIONS)):
            missing = sorted(required - set(shape))
            if missing:
                violations.append(
                    f"{key} (from {detector}) indexes {missing} but emit site "
                    f"#{i} builds only {sorted(shape)}"
                )

    assert not violations, (
        f"{len(violations)} finding shape(s) lack a field their print block "
        "indexes, so the text renderer raises KeyError mid-loop and every "
        "finding printed after it -- plus all informational output -- is lost, "
        "while the exit code stays 1 and --json stays complete: "
        + "; ".join(violations)
    )


# --- end-to-end: the real CLI over real files --------------------------

# A Dockerfile whose final stage pins a tag the README names differently.
# `find_dockerfile_multistage_drift` emits
# {file, doc_image, dockerfile_image, pos} for this shape — no `detail`.
MULTISTAGE_FIXTURE = {
    "Dockerfile": "FROM node:20-slim AS build\nRUN x\nFROM node:20-slim\n",
    "README.md": "Production runs on docker node:22-alpine today.\n",
    ".gitattributes": "* text=auto eol=lf\n",
}

# A workflow pinning setup-python below the pyproject floor.
# `find_python_version_drift` emits `workflow_version`, not `version_file`.
PYTHON_WORKFLOW_FIXTURE = {
    "pyproject.toml": '[project]\nname="d"\nversion="0.1"\nrequires-python=">=3.12"\n',
    ".github/workflows/ci.yml": (
        "jobs:\n  t:\n    steps:\n      - uses: actions/setup-python@v5\n"
        "        with:\n          python-version: '3.9'\n"
    ),
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
        capture_output=True, text=True, encoding="utf-8",
    )


def _findings(root: Path, key: str) -> list[dict]:
    proc = _run(root, "--json")
    assert proc.returncode in (0, 1), f"--json failed: {proc.stderr[-500:]}"
    return [d for d in json.loads(proc.stdout).get(key, []) if isinstance(d, dict)]


def _assert_text_mode_reports(root: Path, key: str) -> None:
    """Text mode must render every finding it gates, without a traceback.

    `--json` is the control: it runs the same detectors, so an empty list here
    means the fixture never fired and the rest of the assertions are vacuous.
    """
    expected = _findings(root, key)
    assert expected, f"fixture did not fire {key}; the rest of this test proves nothing"

    proc = _run(root)
    assert proc.returncode == 1, f"fixture should gate the build; got {proc.returncode}"
    assert "Traceback" not in proc.stderr, (
        "the text renderer crashed, so every finding printed after the offending "
        f"block is lost and the operator gets a traceback instead of a report:\n"
        f"{proc.stderr[-1500:]}"
    )

    missing = [d for d in expected if _marker(d) not in proc.stdout]
    assert not missing, (
        f"{key} trips the exit code and appears in --json but is absent from the "
        f"text output: {[ _marker(d) for d in missing ]}\n--- text ---\n{proc.stdout}"
    )


def _marker(d: dict) -> str:
    """A string identifying one finding in rendered output.

    Prefers the detector's own prose so this does not hardcode a sentence the
    printers are free to reword; falls back to the file the finding is about,
    which every text surface prints.
    """
    return d.get("detail") or d.get("file", "")


def test_multistage_doc_mismatch_shape_reaches_the_text_report(tmp_path: Path) -> None:
    """`cli.py`'s block read `d['detail']`; this shape has none."""
    _assert_text_mode_reports(_write(tmp_path / "ms", MULTISTAGE_FIXTURE),
                              "docker_multistage_drifts")


def test_workflow_python_below_floor_reaches_the_text_report(tmp_path: Path) -> None:
    """`cli.py`'s block read `d['version_file']`; this shape has `workflow_version`."""
    _assert_text_mode_reports(_write(tmp_path / "wf", PYTHON_WORKFLOW_FIXTURE),
                              "python_version_drifts")


def test_conflicting_stage_tags_shape_still_renders(tmp_path: Path) -> None:
    """Positive control: the shape that always worked must keep working.

    Without this the two tests above could pass by deleting the block outright
    and rendering nothing at all.
    """
    root = _write(tmp_path / "ok", {
        "Dockerfile": "FROM node:18-slim AS build\nRUN x\nFROM node:20-slim\n",
        "README.md": "# demo\n",
        ".gitattributes": "* text=auto eol=lf\n",
    })
    findings = _findings(root, "docker_multistage_drifts")
    assert findings, "fixture did not fire; the rest of this test proves nothing"
    proc = _run(root, "--only", "docker-multistage")
    assert proc.returncode == 1, f"should gate the build; got {proc.returncode}"
    assert "Traceback" not in proc.stderr, proc.stderr[-800:]
    # Both shapes reach stdout: the detector's own prose for the conflicting
    # tags, and the stated image pair for the shape that has no prose.
    assert findings[0]["detail"] in proc.stdout, (
        f"the conflicting-tags shape lost its detail line:\n{proc.stdout}"
    )
    assert "18-slim" in proc.stdout and "20-slim" in proc.stdout, proc.stdout