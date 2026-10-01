"""Regression test: the Pages deployment job must be serialized.

`actions/deploy-pages` creates a GitHub Pages deployment through the API, and
the API rejects a second concurrent creation with:

    Deployment request failed for <sha> due to in progress deployment.
    Please cancel <other-sha> first or wait for it to complete.

That is not a flake in the docs build -- it is two deployments racing. GitHub
allows exactly one in-flight Pages deployment per repository, so two pushes to
`main` that land close together (merging a batch of ready PRs is the normal way
this repo moves) make whichever job arrives second fail. The merge itself is
fine and the tests pass; only the deployment step is lost.

The fix is a concurrency group with `cancel-in-progress` on the deploying job,
which both serializes the deployments and drops the stale one. This test pins
that wiring so removing it fails loudly rather than silently reintroducing the
race.
"""

import os
import re

import pytest

CI_WORKFLOW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".github",
    "workflows",
    "ci.yml",
)


@pytest.fixture(scope="module")
def ci_source() -> str:
    with open(CI_WORKFLOW, encoding="utf-8") as fh:
        return fh.read()


def _job_block(source: str, job: str) -> str:
    """Return the YAML block for a single job, up to the next top-level key."""
    match = re.search(
        rf"^  {re.escape(job)}:\n(?P<body>(?:^(?:    .*|\s*)\n?)*)",
        source,
        re.M,
    )
    assert match, f"job '{job}' not found in {CI_WORKFLOW}"
    return match.group("body")


def test_deploy_docs_job_exists(ci_source):
    assert "deploy-docs:" in ci_source, "the Pages deployment job disappeared"


def test_deploy_docs_is_serialized(ci_source):
    """The deploying job must carry a concurrency group.

    Without it, two pushes landing together produce one guaranteed failure.
    """
    body = _job_block(ci_source, "deploy-docs")

    assert "concurrency:" in body, (
        "deploy-docs has no concurrency group: two Pages deployments racing "
        "will make the second one fail with 'due to in progress deployment'"
    )

    # Non-greedy: the group value is a GitHub expression such as
    # `pages-deploy-${{ github.ref }}`, whose braces would otherwise be read as
    # the end of the match.
    group = re.search(r"concurrency:\s*\n\s*group:\s*.+", body)
    assert group, "concurrency: block without a group: key"

    # The group must be keyed on the branch/ref, otherwise a docs build for one
    # commit cancels the deployment of an unrelated one.
    assert "github.ref" in group.group(0) or "refs/heads/main" in group.group(0), (
        f"concurrency group {group.group(0)!r} is not keyed on the ref; "
        "deployments of unrelated refs would cancel each other"
    )


def test_deploy_docs_cancels_the_stale_deployment(ci_source):
    """The superseded deployment should be dropped, not merely queued.

    Queuing is not enough: while a stale deployment waits, its own `test` and
    `docs` jobs are already burning runner minutes for an artifact nobody will
    publish. `cancel-in-progress` also keeps the queue from growing without
    bound when several PRs are merged in a batch.
    """
    body = _job_block(ci_source, "deploy-docs")

    assert re.search(r"cancel-in-progress:\s*(true|false)", body), (
        "deploy-docs concurrency group does not set cancel-in-progress"
    )

    value = re.search(r"cancel-in-progress:\s*(true|false)", body).group(1)
    assert value == "true", (
        "cancel-in-progress is false: a batch of merges would queue every "
        "superseded Pages deployment instead of dropping the stale ones"
    )


def test_only_the_deploying_job_is_serialized(ci_source):
    """Serializing `test` would kill the matrix; the lock belongs to deploy only.

    A workflow-level concurrency group would also cancel the test matrix of a
    newer commit whenever an older commit reaches its deployment step -- which
    silently trades test coverage for deployment throughput. The group belongs
    on the job.
    """
    header = ci_source.split("\njobs:\n")[0]

    assert not re.search(r"^concurrency:", header, re.M), (
        "concurrency group declared at workflow level: it would cancel the test "
        "matrix of newer commits when an older commit reaches deploy-docs"
    )


def test_concurrency_group_is_unique_per_job(ci_source):
    """Two jobs sharing one group would serialize against each other."""
    body = _job_block(ci_source, "deploy-docs")
    groups = re.findall(r"group:\s*(\S+)", body)

    assert len(groups) == 1, f"expected a single group in deploy-docs, found {groups}"