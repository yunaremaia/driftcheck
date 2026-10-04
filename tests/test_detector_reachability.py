"""A detector module that ships in the package must actually run.

`detector.scan_repo` is the only thing that produces a result dict, and it
calls each detector's `find_*` by name. A `find_*` that no call site reaches is
a detector the tool ships but never runs: the CLI reports nothing, `--json` has
no key for it, `--sarif` has no rule, and the exit code ignores it. No error, no
warning -- the finding is simply absent, which for a drift tool is the worst
failure mode there is: a green check run over a repo that really does drift.

`tests/test_uv_lock.py` exercises `find_uv_lock_drift` by calling the function
directly, so it passes while the detector is unreachable in production. That is
the coverage gap these tests close: they assert reachability from `detector.py`,
not correctness of the detector in isolation.

`test_sarif_coverage.py` guards the far end of the pipeline (a key that reaches
`to_sarif` is not dropped there). This file guards the near end (a detector that
exists is called at all). A detector missing from either end is invisible.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "driftcheck"
_DETECTORS = _SRC / "detectors"
_SCANNER = _SRC / "detector.py"


def _defined_finders() -> dict[str, str]:
    """Every ``find_*`` entry point defined in the detectors package.

    Keyed by function name, valued by module name. A duplicate name across
    modules is a separate problem and would collide here, so it is reported
    rather than silently losing one of the two.
    """
    found: dict[str, str] = {}
    for path in sorted(_DETECTORS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "find_"
            ):
                found[node.name] = path.stem
    return found


def _called_by_scanner() -> dict[str, list[int]]:
    """Names ``detector.py`` reaches, mapped to the lines that reach them.

    Three reference forms count as wired, because all three are how the other 90
    detectors are referenced: a bare call ``find_x(...)``, an
    ``import ... as find_x``/``from ... import find_x`` binding, and a
    ``__all__`` re-export string. Matching by identifier rather than by
    ``Call`` node is deliberate -- a detector invoked inside a list
    comprehension or assigned to a local is still wired.

    AST rather than regex: a substring match would also count a mention inside
    a docstring or a comment, which is exactly the false positive that lets an
    unreachable detector look wired up.
    """
    tree = ast.parse(_SCANNER.read_text(encoding="utf-8"))
    called: dict[str, list[int]] = {}

    def note(name: str, lineno: int) -> None:
        if name.startswith("find_"):
            called.setdefault(name, []).append(lineno)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            note(node.id, node.lineno)
        elif isinstance(node, ast.Attribute):
            note(node.attr, node.lineno)
        elif isinstance(node, ast.alias):
            # `from .detectors.x import find_y` / `import ... as find_y`
            note(node.asname or node.name.split(".")[-1], node.lineno)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # `__all__` entries are plain strings, not Name nodes.
            if node.value.startswith("find_"):
                note(node.value, node.lineno)
    return called


DEFINED = _defined_finders()
CALLED = _called_by_scanner()


def test_detectors_are_discovered() -> None:
    """Guard against the extraction silently finding nothing.

    Without this, a broken parser makes every other test in this file pass
    vacuously -- the same failure mode `test_sarif_coverage.py` guards against
    with its own `test_detector_emits_keys`.
    """
    assert len(DEFINED) > 50, f"expected many find_* entry points, parsed {len(DEFINED)}"
    assert "find_uv_lock_drift" in DEFINED, (
        "find_uv_lock_drift vanished from detectors/uv_lock.py -- if it was "
        "intentionally removed, delete this file rather than leaving it inert"
    )


def test_no_duplicate_finder_names() -> None:
    """Two modules defining the same ``find_*`` makes one of them unreachable."""
    by_name: dict[str, list[str]] = {}
    for path in sorted(_DETECTORS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "find_"
            ):
                by_name.setdefault(node.name, []).append(path.stem)
    dupes = {name: mods for name, mods in by_name.items() if len(mods) > 1}
    assert not dupes, f"find_* defined in more than one module: {dupes}"


def test_every_detector_is_reachable_from_the_scanner() -> None:
    """No shipped detector may be defined without `detector.py` calling it."""
    unreachable = sorted(name for name in DEFINED if name not in CALLED)
    assert not unreachable, (
        f"{len(unreachable)} detector(s) are defined but never called by "
        f"detector.py, so they can never report: "
        + ", ".join(f"{n} (detectors/{DEFINED[n]}.py)" for n in unreachable)
        + " -- wire each into scan_repo's result dict or delete the module"
    )


UV_LOCK = """\
version = 1

[[package]]
name = "requests"
version = "2.20.0"
"""

PYPROJECT = """\
[project]
name = "uvfix"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["requests>=2.31.0"]
"""


def test_find_uv_lock_drift_is_wired_into_the_scan(tmp_path: Path) -> None:
    """The concrete instance, asserted through the public scan entry point.

    The static check above says the name is never referenced; this says what
    that costs a user. `find_uv_lock_drift` parses a real `uv.lock` and compares
    it against `pyproject.toml`, so a fixture pinning requests 2.20.0 against a
    `>=2.31.0` constraint is genuine drift and must surface in `scan_repo`'s
    result. Before the fix it did not: the detector was shipped and unit-tested
    in isolation, but nothing in the pipeline ever called it, so the repo
    passed clean in every output mode.
    """
    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "README.md").write_text("# uv fixture\n", encoding="utf-8")

    # Control: the detector does find this, so the assertion below is about
    # reachability, not about the detector's correctness.
    from driftcheck.detectors.uv_lock import find_uv_lock_drift

    assert find_uv_lock_drift(tmp_path), (
        "fixture did not fire -- fix find_uv_lock_drift, not the wiring"
    )

    from driftcheck.detector import scan_repo

    result = scan_repo(tmp_path)
    assert result.get("uv_lock_drifts"), (
        "find_uv_lock_drift detected a real uv.lock/pyproject.toml mismatch but "
        "scan_repo returned no uv_lock_drifts key -- the detector ships in the "
        "package and can never report"
    )