from driftcheck.detectors.actions_version_drift import find_actions_version_drift


def test_detects_documentation_workflow_mismatch():
    workflows = {".github/workflows/ci.yml": "steps:\n  - uses: actions/checkout@v4\n"}
    docs = {"README.md": "CI uses actions/checkout@v3."}
    assert find_actions_version_drift(workflows, docs) == [{
        "file": ".github/workflows/ci.yml",
        "owner_repo": "actions/checkout",
        "workflow_version": "v4",
        "doc_mentions": ["3"],
        "detail": "actions/checkout@v4 in workflows but docs mention ['3']",
    }]


def test_matching_version_is_not_drift():
    workflows = {"ci.yml": "- uses: actions/setup-python@v6"}
    docs = {"CONTRIBUTING.md": "Use actions/setup-python@v6 in CI."}
    assert find_actions_version_drift(workflows, docs) == []


def test_ignores_unversioned_refs_and_unmentioned_actions():
    workflows = {"ci.yml": "- uses: owner/action@main\n- uses: actions/cache@v6"}
    docs = {"README.md": "No action pins are documented here."}
    assert find_actions_version_drift(workflows, docs) == []


def test_collects_documented_versions_across_docs():
    workflows = {"ci.yml": "- uses: actions/checkout@v4"}
    docs = {"README.md": "actions/checkout@v3", "docs/ci.md": "actions/checkout@v2"}
    drift = find_actions_version_drift(workflows, docs)[0]
    assert drift["doc_mentions"] == ["2", "3"]
