"""Classifiers must advertise every Python version the package claims to support.

``requires-python`` is what pip enforces, but PyPI builds its
"Programming Language" filter from the trove classifiers. A package declaring
``requires-python = ">=3.10"`` with only the bare ``Programming Language ::
Python :: 3`` classifier is unfilterable by minor version, so someone searching
PyPI for a 3.12 package does not find it.
"""

import re
from pathlib import Path

import pytest

try:  # tomllib is 3.11+; the package itself depends on tomli below that
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on the 3.10 CI leg
    import tomli as tomllib  # type: ignore[no-redef]

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _project() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]


def _minor_classifiers() -> set[str]:
    return {
        c
        for c in _project()["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c)
    }


def test_classifiers_exist_at_all():
    assert _project()["classifiers"], "a published package needs classifiers"


def test_every_supported_minor_has_a_classifier():
    """Each minor allowed by requires-python must be individually filterable."""
    floor = re.search(r">=\s*3\.(\d+)", _project()["requires-python"])
    assert floor, "this test only knows how to read a >=3.N floor"
    expected = {f"Programming Language :: Python :: 3.{n}" for n in range(int(floor.group(1)), 15)}
    assert _minor_classifiers() >= expected


@pytest.mark.parametrize("minor", ["3.10", "3.12", "3.14"])
def test_named_minor_is_classified(minor):
    assert f"Programming Language :: Python :: {minor}" in _project()["classifiers"]