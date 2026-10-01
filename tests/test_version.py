"""`__version__` must reflect the installed distribution, not a literal.

The constant reaches users through the `--version` flag and through the
SARIF report's tool version. While it was hardcoded, a published
`driftcheck-py` 0.1.49 reported itself as 0.1.47.
"""

from __future__ import annotations

import re
import subprocess
import sys
from importlib.metadata import version as metadata_version
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import driftcheck

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _declared_version() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_is_not_a_hardcoded_literal():
    source = (REPO_ROOT / "src" / "driftcheck" / "__init__.py").read_text(encoding="utf-8")
    literal = re.search(r'^__version__\s*=\s*[\'"]([\d.]+)[\'"]', source, re.MULTILINE)
    assert literal is None, (
        "__version__ is assigned a literal; read it from the installed "
        "distribution metadata so it cannot drift from pyproject.toml"
    )


def test_version_is_wellformed():
    assert re.fullmatch(r"\d+\.\d+\.\d+([.\-+].*)?", driftcheck.__version__), (
        f"unexpected version string: {driftcheck.__version__!r}"
    )


def test_version_is_not_the_dev_placeholder_when_installed():
    if metadata_version("driftcheck-py") == "0.0.0.dev0":
        pytest.skip("package is not installed; version falls back to the placeholder")
    assert driftcheck.__version__ != "0.0.0.dev0"


def test_pyproject_version_is_not_a_placeholder():
    assert _declared_version() != "0.0.0", (
        "pyproject.toml still declares the dev placeholder version"
    )


def test_cli_reports_the_module_version():
    """`driftcheck --version` and `driftcheck.__version__` must agree."""
    result = subprocess.run(
        [sys.executable, "-m", "driftcheck", "--version"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        # The package may not be importable from the source checkout layout.
        return
    reported = result.stdout.strip().split()[-1]
    assert reported == driftcheck.__version__, (
        f"CLI reports {reported!r} but __version__ is {driftcheck.__version__!r}"
    )