"""Regression guard for the PyPI publish workflow configuration.

driftcheck is published on PyPI under the distribution name `driftcheck-py`
(the bare name `driftcheck` belongs to an unrelated third-party package), so
the documentation must offer `pip install driftcheck-py` and carry the version
badge for that name. An earlier release of this suite asserted the opposite:
it forbade every PyPI install path and every `img.shields.io/pypi` badge,
which was correct only while the package was unpublished. That guard is now
inverted -- see the three doc guards at the bottom of this file.

A broken release run is invisible until a tag is pushed, so the workflow
contract is asserted here to surface any future regression in CI instead.

The workflow is parsed as plain text because PyYAML is not a dependency of
this project, and it avoids the `on:` -> `True` YAML 1.1 boolean trap.
"""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
README = REPO_ROOT / "README.md"
DOC_FILES = ("README.md", "docs/index.md", "docs/getting-started.md")

#: The distribution name actually published on PyPI. The bare name
#: `driftcheck` is taken by another author, so `pip install driftcheck`
#: installs a foreign program instead of this tool.
PUBLISHED_NAME = "driftcheck-py"

#: Version badge for the published distribution. The per-month *downloads*
#: badge is deliberately absent: shields.io's pypi/dm endpoint is rate
#: limited by upstream and pepy.tech 404s, so both render broken images.
VERSION_BADGE = f"https://img.shields.io/pypi/v/{PUBLISHED_NAME}"

#: Matches the short name only when it is NOT the `-py` suffix: the negative
#: lookahead rejects `pip install driftcheck-py`, which is the correct line.
#: A plain substring test for "pip install driftcheck" matches BOTH spellings,
#: so it would reject the command it is supposed to mandate.
SHORT_NAME_INSTALL = re.compile(
    r"pip(?:3)?\s+install\s+(?:.*\s)?driftcheck(?![\w-])"
)

#: A git URL in an install line is a legitimate from-source install and must
#: keep passing.
GIT_INSTALL = "git+"


def _read_text(path):
    """Read a repo file as UTF-8.

    The encoding is explicit because Windows defaults to cp1252, which cannot
    decode characters in the Markdown files. Undecodable bytes are replaced
    rather than raising, so an encoding problem can never mask a real finding.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def _workflow_text():
    return _read_text(PUBLISH_WORKFLOW)


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


def _numbered_offenders(path, needle, should_contain):
    """Line references in `path` that mention `needle` but not `should_contain`.

    The needle must be specific enough to exclude unrelated lines: a bare
    `pip install` sweep flags `pip install pre-commit` and every legitimate
    from-source `git+` install, which are both correct as written.
    """
    if not path.exists():
        return []
    return [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(_read_text(path).splitlines(), start=1)
        if needle in line
        and should_contain not in line
        and GIT_INSTALL not in line
    ]


def test_readme_offers_pypi_install():
    """The Quickstart must lead with the real PyPI distribution name."""
    install_line = f"pip install {PUBLISHED_NAME}"
    assert install_line in _read_text(README), (
        f"README.md must contain the line `{install_line}`: the package is "
        "published on PyPI under that name (the bare `driftcheck` name belongs "
        "to an unrelated third-party package)"
    )
    offenders = _numbered_offenders(README, "install driftcheck", install_line)
    assert not offenders, (
        "README.md offers an install line that is not "
        f"`{install_line}`:\n" + "\n".join(offenders)
    )


def test_readme_has_pypi_version_badge():
    """The version badge must point at the published distribution name."""
    assert VERSION_BADGE in _read_text(README), (
        f"README.md must contain the badge {VERSION_BADGE}"
    )
    offenders = _numbered_offenders(README, "img.shields.io/pypi", VERSION_BADGE)
    assert not offenders, (
        "README.md carries a PyPI badge for a name that is not the published "
        f"distribution `{PUBLISHED_NAME}`:\n" + "\n".join(offenders)
    )


def test_docs_never_install_the_short_name():
    """`pip install driftcheck` installs another author's package."""
    offenders = []
    for relative in DOC_FILES:
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        for number, line in enumerate(_read_text(path).splitlines(), start=1):
            if SHORT_NAME_INSTALL.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, (
        f"`pip install driftcheck` installs a third-party package, not this "
        f"tool; the published distribution is `{PUBLISHED_NAME}`:\n"
        + "\n".join(offenders)
    )


def test_docs_do_not_claim_it_is_unpublished():
    """The 'not published yet' note became false when the release landed."""
    stale = ("not published on pypi", "not on pypi", "not yet published")
    offenders = []
    for relative in DOC_FILES:
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        for number, line in enumerate(_read_text(path).splitlines(), start=1):
            lowered = line.lower()
            if any(phrase in lowered for phrase in stale):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, (
        "documentation still says the package is unpublished; it is on PyPI "
        f"as `{PUBLISHED_NAME}`\n" + "\n".join(offenders)
    )


def test_docs_install_line_matches_pyproject_name():
    """The documented install target must be the name pyproject publishes."""
    text = _read_text(PYPROJECT)
    declared = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert declared, "pyproject.toml must declare a [project] name"
    name = declared.group(1)
    install_line = f"pip install {name}"
    missing = [
        relative
        for relative in DOC_FILES
        if (REPO_ROOT / relative).exists()
        and not any(
            install_line in line and GIT_INSTALL not in line
            for line in _read_text(REPO_ROOT / relative).splitlines()
        )
    ]
    assert not missing, (
        f"pyproject.toml publishes `{name}`, so these docs must offer "
        f"`{install_line}`:\n" + "\n".join(missing)
    )