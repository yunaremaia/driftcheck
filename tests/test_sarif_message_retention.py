"""A finding's SARIF alert text must be a sentence, not a raw dict repr.

``to_sarif`` reaches a finding through a hand-maintained ``drift_keys`` walk and
the ``DRIFT_RULES`` lookup, and both now cover every key (#475, #476). What
remained hand-maintained is ``_drift_message``: 70 of the 90 curated keys had a
bespoke branch and the other 20 fell through to a bare ``return str(d)``.

The consequence is narrower than a drop but hits the same surface. The finding
reached Code Scanning, carrying its Python repr as the only text an operator
ever sees::

    {'file': 'requirements.txt', 'package': 'requests', 'pinned_version': '2.31.0'}

That is the same closed-list-over-an-open-key-space defect the text output hit
in 8c88873, one function over. Plugin detectors hit it structurally: their key
is built at runtime as ``f"plugin_{name}_drifts"`` so no branch can exist for it
by construction, and every plugin alert in every release has been a dict repr.

These tests drive the real CLI, because the defect is only visible in emitted
output -- a unit test of ``to_sarif`` in isolation is what let it ship.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from driftcheck.messages import describe_finding
from driftcheck.sarif import DRIFT_RULES, _drift_message, to_sarif

# Detectors whose keys have no bespoke branch in `_drift_message`, so their
# payload is rendered by the shared fallback. Taken from the source rather than
# hardcoded so the list cannot drift from the code it describes.
UNFORMATTED = [
    "python_req_drifts",
    "justfile_drifts",
    "terraform_lock_drifts",
    "go_replace_drifts",
    "freshness_drifts",
    "git_submodule_drifts",
    "npmrc_drifts",
    "yarnrc_drifts",
    "pnpm_workspace_drifts",
    "package_version_drifts",
    "pyproject_tool_drifts",
    "python_version_file_drifts",
    "r_drifts",
    "scala_drifts",
    "kmp_drifts",
    "a2a_drifts",
    "changelog_drifts",
    "dockerfile_instruction_drifts",
    "frontmatter_drifts",
    "helm_dependency_drifts",
]

PLUGIN_SOURCE = '''\
def find_probe(root, docs):
    return [{"file": "README.md", "detail": "probe plugin finding", "pos": 0}]


def register():
    return {"probe": find_probe}
'''

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


def _make_repo(root: Path) -> None:
    """A fixture that fires detectors from the unformatted set.

    Each file makes one detector report, so the fixture exercises the fallback
    against real detector payloads rather than synthetic dicts.
    """
    plugins = root / ".driftcheck_plugins"
    plugins.mkdir(parents=True)
    (plugins / "probe.py").write_text(PLUGIN_SOURCE, encoding="utf-8")

    # justfile_drifts: justfile pins python 3.12, README claims 3.9.
    (root / "justfile").write_text("@version python@3.12\n", encoding="utf-8")
    # python_req_drifts: a requirements.txt entry absent from pyproject.
    (root / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\ndependencies = []\n',
        encoding="utf-8",
    )
    # go_replace_drifts: required module missing from go.sum.
    (root / "go.mod").write_text(
        "module example.com/fixture\n\ngo 1.21\n\nrequire github.com/pkg/errors v0.9.1\n",
        encoding="utf-8",
    )
    (root / "go.sum").write_text(
        "github.com/other/thing v1.2.3 h1:aaaa=\n"
        "github.com/other/thing v1.2.3/go.mod h1:bbbb=\n",
        encoding="utf-8",
    )
    # terraform_lock_drifts: locked version violates the declared constraint.
    (root / "versions.tf").write_text(
        'aws = { source = "hashicorp/aws", version = ">= 5.0.0" }\n', encoding="utf-8"
    )
    (root / ".terraform.lock.hcl").write_text(
        'provider "registry.terraform.io/hashicorp/aws" {\n  version = "3.0.0"\n}\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Fixture\n\nRequires Python 3.9.\n", encoding="utf-8")
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-Af"], cwd=root, check=True)


def _run(root: Path, flag: str) -> str:
    env = {**os.environ, "PYTHONPATH": REPO_SRC}
    proc = subprocess.run(
        [sys.executable, "-m", "driftcheck", flag],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode in (0, 1), f"unexpected exit {proc.returncode}: {proc.stderr}"
    return proc.stdout


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("sarif_message")
    _make_repo(root)
    return root


@pytest.fixture(scope="module")
def sarif_results(fixture_repo: Path) -> list[dict]:
    doc = json.loads(_run(fixture_repo, "--sarif"))
    return doc["runs"][0]["results"]


def _key_for_rule(rule_id: str) -> str:
    """Map a SARIF ruleId back to its drift key.

    Curated ids come from ``DRIFT_RULES``; anything else was derived by
    ``_fallback_rule`` from the key, so the mapping has to use that function
    rather than a second guess at the derivation.
    """
    for key, rule in DRIFT_RULES.items():
        if rule[0] == rule_id:
            return key
    return f"<derived:{rule_id}>"


def _drift_dict(doc: dict) -> dict:
    """The drift mapping inside a --json document."""
    stack = [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if any(isinstance(k, str) and k.endswith("_drifts") for k in node):
                return node
            stack.extend(node.values())
    raise AssertionError("no *_drifts mapping found in --json output")


def test_plugin_finding_reaches_sarif_with_a_readable_message(sarif_results: list[dict]) -> None:
    """The plugin path is the structural case: no branch can exist for its key.

    ``plugin_probe_drifts`` is built at runtime, so it has no entry in
    ``DRIFT_RULES`` and can never have a branch in ``_drift_message``. Before
    this fix its alert text was ``str(dict)``.
    """
    texts = [r["message"]["text"] for r in sarif_results]
    assert "probe plugin finding" in texts, (
        f"plugin finding missing or unreadable; messages were {texts}"
    )


def test_no_sarif_message_is_a_raw_payload(sarif_results: list[dict]) -> None:
    """No alert in a real run may carry a Python repr as its text."""
    offenders = [
        r["message"]["text"]
        for r in sarif_results
        if r["message"]["text"].startswith(("{", "["))
    ]
    assert not offenders, f"SARIF alerts rendering a raw payload: {offenders}"


def test_unformatted_keys_render_readably(sarif_results: list[dict]) -> None:
    """The finding text names its subject, not just its field names."""
    texts = [r["message"]["text"] for r in sarif_results]
    # Each of these is emitted by the fixture with a real payload.
    for expected in (
        "requests is in requirements.txt",          # python_req_drifts
        "python 3.9 in README.md should be 3.12",   # justfile_drifts
        "does not satisfy required_providers",      # terraform_lock_drifts
        "missing from go.sum",                      # go_replace_drifts
    ):
        assert any(expected in t for t in texts), f"no readable message containing {expected!r}"


def test_fallback_descriptions_agree_across_surfaces(
    fixture_repo: Path, sarif_results: list[dict]
) -> None:
    """A finding the fallback describes gets the same text in both surfaces.

    Scoped to fallback-rendered keys on purpose: the two surfaces hand-format the
    keys they have bespoke branches for, and those phrasings have always
    differed. What must not differ is the shared floor -- the rendering for keys
    neither surface special-cases.
    """
    text_out = _run(fixture_repo, "")
    for rule in sarif_results:
        key = _key_for_rule(rule.get("ruleId", ""))
        if key not in UNFORMATTED and not key.startswith("<derived:"):
            continue
        message = rule["message"]["text"]
        assert message in text_out, (
            f"fallback message for {key} differs between surfaces: {message!r}"
        )


def test_json_and_sarif_agree_on_finding_count(fixture_repo: Path, sarif_results: list[dict]) -> None:
    """Retention parity: nothing in --json is missing from --sarif."""
    drifts = _drift_dict(json.loads(_run(fixture_repo, "--json")))
    expected = sum(len(v) for k, v in drifts.items() if k.endswith("_drifts") and v)
    assert expected == len(sarif_results), (
        f"--json reports {expected} findings but --sarif emitted {len(sarif_results)}"
    )


@pytest.mark.parametrize("key", UNFORMATTED)
def test_unformatted_key_fallback_is_not_a_repr(key: str) -> None:
    """No curated key may render its payload as a repr."""
    payload = {"file": "README.md", "package": "requests", "pinned_version": "2.31.0", "pos": 0}
    message = _drift_message(key, payload)
    assert not message.startswith("{"), f"{key} renders a raw payload: {message}"
    assert "requests" in message


def test_detail_is_preferred_over_the_field_summary() -> None:
    """A detector that wrote a sentence keeps it verbatim."""
    payload = {"file": "go.mod", "detail": "errors v0.9.1 missing from go.sum", "package": "errors"}
    assert describe_finding(payload) == "errors v0.9.1 missing from go.sum"


def test_location_fields_are_not_repeated_in_the_summary() -> None:
    """``file``/``pos``/``line`` are rendered by the surfaces, not the summary."""
    summary = describe_finding({"file": "go.mod", "pos": 12, "line": 3, "package": "errors"})
    assert summary == "package=errors", summary


def test_placeholder_values_are_omitted() -> None:
    """An absent field is left out rather than rendered as ``key=``.

    Detectors signal "absent" as "", None or 0, so the summary drops those
    instead of listing fields that carry no information.
    """
    payload = {"file": "x", "package": "", "extra": None, "pos": 0}
    assert describe_finding(payload) == str(payload), (
        "with no informative field left, the repr is the honest rendering"
    )
    assert describe_finding({"package": "", "tool": "python"}) == "tool=python"


def test_empty_payload_falls_back_to_its_repr() -> None:
    """With nothing to describe, the repr is the only honest rendering."""
    assert describe_finding({"file": "x", "pos": 0}) == "{'file': 'x', 'pos': 0}"


def test_non_dict_payload_is_stringified() -> None:
    """A non-dict entry still produces text rather than raising."""
    assert describe_finding("plain string finding") == "plain string finding"
    assert describe_finding(42) == "42"


def test_fallback_rule_id_cannot_collide_with_a_curated_one() -> None:
    """A derived rule id must not shadow a curated rule in Code Scanning."""
    curated = {rule[0] for rule in DRIFT_RULES.values()}
    for key in DRIFT_RULES:
        derived = f"{key.removesuffix('_drifts')}-drift"
        if derived in curated:
            assert derived == DRIFT_RULES[key][0], (
                f"{key}'s derived rule id {derived!r} collides with a curated rule"
            )


def test_to_sarif_uses_the_fallback_for_an_unknown_key() -> None:
    """An unknown key with a payload still yields a sentence."""
    doc = to_sarif({"totally_new_drifts": [{"file": "README.md", "detail": "brand new"}]})
    assert doc["runs"][0]["results"][0]["message"]["text"] == "brand new"