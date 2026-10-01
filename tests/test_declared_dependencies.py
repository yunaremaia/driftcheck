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
_BUILTIN = set(sys.stdlib_module_names) | {
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


def _imported_top_level_modules() -> dict[str, list[str]]:
    """Map every non-stdlib top-level import to the files that use it."""
    found: dict[str, list[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root.lower() not in _BUILTIN:
                        found.setdefault(root, []).append(relative)
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative import within the package
                    continue
                root = (node.module or "").split(".")[0]
                if root and root.lower() not in _BUILTIN:
                    found.setdefault(root, []).append(relative)
    return found


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


def test_declared_dependencies_are_actually_imported():
    """The reverse check: a declared dependency nothing imports is dead weight."""
    declared = _distribution_names(_declared_requirements())
    imported = {module.lower() for module in _imported_top_level_modules()}
    unused = sorted(
        name
        for name in declared
        if name not in imported
        and _ALIASES.get(name) not in imported
    )
    assert not unused, (
        "declared dependencies that nothing in the package imports: "
        f"{unused}"
    )