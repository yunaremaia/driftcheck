"""Regression guard for the PyPI publish workflow configuration.

driftcheck has never been published to PyPI: every release run of
.github/workflows/publish.yml failed with `invalid-publisher` because no
trusted publisher is registered on pypi.org for this project. That class of
breakage is invisible until a tag is pushed, so the workflow contract is
asserted here to surface any future regression in CI instead.

The workflow is parsed as plain text because PyYAML is not a dependency of
this project, and it avoids the `on:` -> `True` YAML 1.1 boolean trap.
"""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"


def _workflow_text():
    return PUBLISH_WORKFLOW.read_text()


def _block_after(text, key):
    """Return the indented block that follows a top-level `key:` line."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.rstrip() == f"{key}:":
            block = []
            for following in lines[index + 1:]:
                if following.strip() and not following.startswith((" ", "\t")):
                    break
                block.append(following)
            return "\n".join(block)
    raise AssertionError(f"{key}: block not found in {PUBLISH_WORKFLOW}")


def test_publish_workflow_grants_id_token_write():
    """Trusted publishing needs the OIDC token permission at workflow level."""
    permissions = _block_after(_workflow_text(), "permissions")
    assert re.search(r"^\s*id-token:\s*write\s*$", permissions, re.MULTILINE), (
        "publish.yml must grant 'id-token: write' under permissions: "
        "PyPI trusted publishing authenticates via OIDC and fails without it"
    )


def test_publish_workflow_uses_pypa_publish_action():
    text = _workflow_text()
    assert "pypa/gh-action-pypi-publish" in text, (
        "publish.yml must upload with the pypa/gh-action-pypi-publish action"
    )


def test_publish_workflow_triggers_on_published_release():
    triggers = _block_after(_workflow_text(), "on")
    assert re.search(r"^\s*release:\s*$", triggers, re.MULTILINE), (
        "publish.yml must trigger on the 'release' event"
    )
    assert re.search(r"types:\s*\[.*published.*\]", triggers), (
        "publish.yml must only publish on release type 'published', so drafts "
        "and edits do not attempt an upload"
    )


def test_publish_workflow_declares_pypi_environment():
    """The environment name must match the trusted publisher on pypi.org."""
    text = _workflow_text()
    scalar = re.search(r"^\s+environment:\s*pypi\s*$", text, re.MULTILINE)
    mapping = re.search(
        r"^\s+environment:\s*$\n^\s+name:\s*pypi\s*$", text, re.MULTILINE
    )
    assert scalar or mapping, (
        "the publish job must declare environment 'pypi'; PyPI matches the "
        "trusted publisher on that environment name"
    )


def test_docs_do_not_promise_pypi_install():
    """driftcheck is not on PyPI, so no doc may offer a PyPI install path."""
    offenders = []
    for relative in ("README.md", "docs/index.md", "docs/getting-started.md"):
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if "pip install driftcheck" in stripped and "git+" not in stripped:
                offenders.append(f"{relative}:{number}: {stripped}")
            if "img.shields.io/pypi" in stripped:
                offenders.append(f"{relative}:{number}: {stripped}")
    assert not offenders, (
        "documentation promises a PyPI release that does not exist:\n"
        + "\n".join(offenders)
    )
