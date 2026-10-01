"""The published wheel must import in a clean environment.

`pip install -e .` in CI resolves the project itself but never proves that
`dependencies` in pyproject.toml lists everything the package imports. The
2026-10-01 release of `driftcheck-py` shipped with `dependencies = []` while
`driftcheck.detectors.python_freshness` imports `packaging`, so every
`pip install driftcheck-py` from PyPI crashed on first run with
`ModuleNotFoundError: No module named 'packaging'`.

These tests read the declared dependencies and cross-check them against the
third-party imports actually present in the source tree, so the omission is
caught here rather than by a user.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SOURCE_ROOT = REPO_ROOT / "src" / "driftcheck"

# Modules that are either in the standard library or vendored by setuptools,
# and therefore must never appear in `dependencies`.
_VENDORED = {
    "driftcheck",
    "setuptools",
    "pkg_resources",
    "_distutils_hack",
}

# `tomllib` is stdlib from 3.11 onwards and the third-party `tomli` shim on 3.10.
# The detectors import it through a try/except ImportError fallback, so the AST
# walk always sees both spellings regardless of the running interpreter. Either
# name satisfies the other, and on the 3.10 CI leg neither is in
# `sys.stdlib_module_names`, so `tomllib` must not be reported as undeclared.
_ALIASES = {"tomllib": "tomli", "tomli": "tomllib"}


def _is_declared(module: str, declared: set[str]) -> bool:
    """True when `module`, or its interchangeable alias, is declared."""
    if module.lower() in declared:
        return True
    alias = _ALIASES.get(module.lower())
    return alias is not None and alias in declared


def _is_unused(name: str, imported: set[str]) -> bool:
    """True when nothing imports `name`, or its interchangeable alias.

    The mirror of `_is_declared`: the two spellings of the TOML reader must
    satisfy each other in both directions, otherwise whichever name the
    running interpreter does not provide gets reported as dead weight.
    """
    if name in imported:
        return False
    alias = _ALIASES.get(name)
    return alias is None or alias not in imported


def _declared_requirements() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return list(data.get("project", {}).get("dependencies", []))


def _distribution_names(requirements: list[str]) -> set[str]:
    """Map requirement specifiers to importable top-level module names."""
    names = set()
    for requirement in requirements:
        name = requirement.split(";")[0]
        for separator in ("[", "<", ">", "=", "!", "~", " "):
            name = name.split(separator)[0]
        if name:
            names.add(name.strip().lower())
    return names


def _imported_top_level_modules(
    builtin: set[str] | None = None,
) -> dict[str, list[str]]:
    """Map every non-stdlib top-level import to the files that use it.

    `builtin` overrides the builtin module set so a test can simulate a
    runner on a different Python version.
    """
    if builtin is None:
        builtin = set(sys.stdlib_module_names) | _VENDORED
    found: dict[str, list[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root.lower() not in builtin:
                        found.setdefault(root, []).append(relative)
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative import within the package
                    continue
                root = (node.module or "").split(".")[0]
                if root and root.lower() not in builtin:
                    found.setdefault(root, []).append(relative)
    return found


def test_interchangeable_toml_names_satisfy_each_other():
    """`tomllib` and `tomli` must be interchangeable in both directions.

    The detectors spell the module both ways through an import fallback, so
    the AST walk sees both names no matter which interpreter runs. Whichever
    of the two the runner cannot provide is covered by the other: on 3.11+
    the stdlib `tomllib` satisfies the declared `tomli`, and on 3.10 the
    declared `tomli` satisfies the missing `tomllib`.
    """
    # forward: an undeclared `tomllib` is covered by the declared `tomli`
    assert _is_declared("tomllib", {"tomli"})
    assert not _is_declared("tomllib", {"packaging"})
    # reverse: a declared `tomli` counts as used when only `tomllib` is imported
    assert not _is_unused("tomli", {"tomllib"})
    assert not _is_unused("tomllib", {"tomli"})
    # an unrelated name is never rescued by the alias, in either direction
    assert not _is_declared("packaging", {"tomli"})
    assert _is_unused("packaging", {"tomllib"})


def test_declared_dependencies_are_not_empty():
    """A CLI that imports third-party packages must declare them."""
    assert _declared_requirements(), (
        "project.dependencies is empty but the package imports third-party "
        "modules; anything installed from PyPI will crash on first run"
    )


def test_every_imported_module_is_declared():
    """Every third-party import must be covered by a declared dependency."""
    declared = _distribution_names(_declared_requirements())
    missing = {}
    for module, files in _imported_top_level_modules().items():
        if not _is_declared(module, declared):
            missing[module] = files
    assert not missing, (
        "pyproject.toml does not declare every imported third-party module; "
        "the built wheel will fail to import after `pip install`:\n"
        + "\n".join(
            f"  {module} (used by {', '.join(files)})" for module, files in missing.items()
        )
        + f"\n  declared: {sorted(declared)}"
    )


def _missing_modules(
    declared: set[str],
    builtin: set[str] | None = None,
) -> dict[str, list[str]]:
    """Third-party imports that no declared dependency covers."""
    return {
        module: files
        for module, files in _imported_top_level_modules(builtin).items()
        if not _is_declared(module, declared)
    }


def _simulated_310_builtin() -> set[str]:
    """The builtin module set a Python 3.10 runner would report.

    `sys.stdlib_module_names` only lists the standard library of the
    interpreter running the tests, and `tomllib` joined the stdlib in 3.11,
    so the set has to be corrected explicitly to exercise the 3.10 CI legs
    from any runner.
    """
    return (set(sys.stdlib_module_names) | _VENDORED) - {"tomllib"}


def test_stdlib_only_on_newer_pythons_is_not_reported_as_undeclared():
    """Regression: the 3.10 CI leg must not demand `tomllib`.

    Every 3.10 leg of the matrix failed on all three platforms with "does
    not declare every imported third-party module: tomllib" even though
    `pip install` pulls the declared `tomli` shim that provides it there.
    """
    # The simulated runner must differ from the real one by exactly `tomllib`,
    # otherwise this test would be exercising the wrong runner.
    simulated = _simulated_310_builtin()
    real = set(sys.stdlib_module_names) | _VENDORED
    assert simulated == real - {"tomllib"}, (
        "the simulated 3.10 builtin set must be the real one minus tomllib; "
        f"got a difference of {sorted(real.symmetric_difference(simulated))}"
    )
    if sys.version_info >= (3, 11):
        # Only meaningful on a runner where `tomllib` is genuinely present:
        # the subtraction above is what makes the simulation bite.
        assert "tomllib" in real, (
            "this test assumes tomllib is standard library from 3.11 onwards"
        )

    missing = _missing_modules(
        _distribution_names(_declared_requirements()),
        simulated,
    )
    assert "tomllib" not in missing, (
        "tomllib is standard library from Python 3.11 onwards; on older "
        "routers the declared tomli shim covers it"
    )
    assert not missing, (
        "a 3.10 runner must not report any undeclared third-party import, "
        f"but reported: {sorted(missing)}"
    )


def test_dropping_the_tomli_shim_is_still_reported_on_older_pythons():
    """The alias must not paper over a genuinely missing declaration.

    Guards the fix above from being trivially satisfied by whitelisting
    `tomllib`: without the `tomli` dependency a 3.10 wheel has nothing
    providing that module, so the omission must still be reported.
    """
    declared = _distribution_names(_declared_requirements()) - {"tomli"}
    missing = _missing_modules(declared, _simulated_310_builtin())
    assert "tomllib" in missing, (
        "without the tomli dependency a Python 3.10 wheel cannot provide "
        "tomllib, so the omission must be reported"
    )


def test_tomli_is_not_reported_as_unused_on_a_310_runner():
    """The reverse check must survive the alias too.

    On a 3.10 runner `tomllib` is a third-party import that the declared
    `tomli` satisfies, so `tomli` counts as used and must not be flagged as
    dead weight.

    The AST walk sees whichever spelling the detectors actually wrote, so
    the real import set may well contain `tomli` directly. The scenario
    that needs the alias is a runner where only `tomllib` is reported, so
    the alias is exercised explicitly rather than left to chance.
    """
    declared = _distribution_names(_declared_requirements())
    imported = {
        module.lower()
        for module in _imported_top_level_modules(_simulated_310_builtin())
    }

    # A runner that only reports `tomllib`: the declared `tomli` has to be
    # rescued by the alias, or it is dead weight.
    only_tomllib = {"tomllib"}
    assert not _is_unused("tomli", only_tomllib), (
        "the alias must let a declared tomli satisfy an imported tomllib"
    )
    # ...and the alias must not rescue an unrelated name.
    assert _is_unused("packaging", only_tomllib), (
        "an unrelated dependency is never rescued by the TOML alias"
    )

    unused = sorted(name for name in declared if _is_unused(name, imported))
    assert "tomli" not in unused, (
        "tomli is imported on Python 3.10 through the detectors' "
        "import tomllib / except ImportError fallback"
    )


def test_declared_dependencies_are_actually_imported():
    """The reverse check: a declared dependency nothing imports is dead weight."""
    declared = _distribution_names(_declared_requirements())
    imported = {module.lower() for module in _imported_top_level_modules()}
    unused = sorted(name for name in declared if _is_unused(name, imported))
    assert not unused, (
        "declared dependencies that nothing in the package imports: "
        f"{unused}"
    )