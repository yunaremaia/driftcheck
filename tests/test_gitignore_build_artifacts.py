"""Regression guard: build artifacts must stay out of git.

`python -m build` (run by `.github/workflows/publish.yml`) and `pip install -e .`
both write generated trees into the repository, and neither was covered by
`.gitignore`:

* line 3 pinned the egg-info directory to `src/driftcheck.egg-info/`, the name
  the package had *before* it was renamed. The distribution is `driftcheck-py`
  (`pyproject.toml`), so setuptools writes `src/driftcheck_py.egg-info/` and
  the rule matched nothing.
* `build/` was absent entirely. It holds `build/lib/driftcheck/`, a full stale
  copy of the importable package: 98 modules that drift from `src/` and are
  not importable in any meaningful sense.

The consequence is silent until someone runs `git add -A`: both trees are
staged, and the stale duplicate package ships in the same commit as its
original. This guards the rule with `git check-ignore` against a throwaway
repository seeded with the real `.gitignore`, so a rename or a packaging
change that reintroduces the gap fails here instead of in a commit.

The egg-info directory name is derived from `[project] name` rather than
hardcoded, so renaming the distribution does not require editing this test.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = REPO_ROOT / ".gitignore"
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: Artifact trees that a build or an editable install leaves in the repo.
BUILD_ARTIFACTS = (
    "build/lib/driftcheck/cli.py",
    "build/bdist.linux-x86_64/driftcheck",
    "dist/driftcheck_py-0.1.50-py3-none-any.whl",
)

#: Entries that must keep working; a rewrite of the file that drops one of
#: these is as much a regression as adding an uncovered tree.
PREVIOUSLY_IGNORED = (
    "site/index.html",
    ".pytest_cache/v/cache/lastfailed",
    "src/driftcheck/__init__.pyc",
)


def _distribution_name() -> str:
    """Return the normalized distribution name declared in pyproject.toml.

    PEP 503 normalization is what setuptools uses to pick the egg-info
    directory: runs of `-`, `_` and `.` collapse to a single `_`.
    """
    text = PYPROJECT.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml must declare a [project] name"
    return re.sub(r"[-_.]+", "_", match.group(1)).lower()


def _seeded_repo(tmp_path: Path) -> Path:
    """Create a throwaway git repo carrying the real .gitignore."""
    subprocess.run(["git", "init", "--quiet", "."], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(
        GITIGNORE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def _is_ignored(repo: Path, relative: str) -> bool:
    """Ask git whether `relative` is excluded by the repo's .gitignore."""
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(
            f"git check-ignore failed for {relative!r}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.returncode == 0


@pytest.fixture(scope="module")
def seeded_repo(tmp_path_factory) -> Path:
    return _seeded_repo(tmp_path_factory.mktemp("gitignore-guard"))


@pytest.mark.parametrize("artifact", BUILD_ARTIFACTS)
def test_build_artifacts_are_ignored(seeded_repo: Path, artifact: str):
    """A `git add -A` must not stage the build tree or the wheel output."""
    assert _is_ignored(seeded_repo, artifact), (
        f"{artifact!r} is not ignored by .gitignore; `git add -A` would stage "
        "generated build output, including the stale duplicate package under "
        "build/lib/"
    )


def test_egg_info_dir_for_the_current_distribution_is_ignored(seeded_repo: Path):
    """The egg-info rule must follow the name pyproject actually declares.

    The rule used to name `driftcheck.egg-info` while the distribution is
    `driftcheck-py`, so it stopped matching the day the package was renamed.
    Deriving the expected directory from `[project] name` keeps the guard
    honest across future renames.
    """
    artifact = f"src/{_distribution_name()}.egg-info/SOURCES.txt"
    assert _is_ignored(seeded_repo, artifact), (
        f"{artifact!r} is not ignored by .gitignore; the egg-info rule is "
        "pinned to a name that no longer matches [project] name in "
        "pyproject.toml, so an editable install leaves generated metadata in "
        "the working tree"
    )


@pytest.mark.parametrize("path", PREVIOUSLY_IGNORED)
def test_existing_ignore_rules_still_apply(seeded_repo: Path, path: str):
    """Broadening the rules must not drop the ones already in place."""
    assert _is_ignored(seeded_repo, path), (
        f"{path!r} is no longer ignored; the .gitignore rewrite dropped a rule "
        "that was previously covered"
    )


def test_source_tree_is_not_ignored(seeded_repo: Path):
    """The guard must not over-reach and ignore the package itself."""
    assert not _is_ignored(seeded_repo, "src/driftcheck/detector.py"), (
        "src/driftcheck/detector.py is ignored; the build-artifact rules are "
        "too broad and would hide the importable package from git"
    )
