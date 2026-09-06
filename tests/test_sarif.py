"""Tests for driftcheck SARIF output generation."""
import json

from driftcheck.sarif import to_sarif


def test_sarif_no_drift():
    result = {
        "toolchain_version": "1.96.1",
        "drifts": [],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result, version="0.1.24")
    assert doc["version"] == "2.1.0"
    assert "2.1.0" in doc["$schema"]
    assert len(doc["runs"]) == 1
    assert doc["runs"][0]["tool"]["driver"]["name"] == "driftcheck"
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def test_sarif_rust_drift():
    result = {
        "toolchain_version": "1.96.1",
        "drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1", "pos": 10}],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    assert len(doc["runs"][0]["tool"]["driver"]["rules"]) == 1
    assert doc["runs"][0]["tool"]["driver"]["rules"][0]["id"] == "rust-toolchain-version-drift"
    assert len(doc["runs"][0]["results"]) == 1
    assert doc["runs"][0]["results"][0]["ruleId"] == "rust-toolchain-version-drift"
    assert doc["runs"][0]["results"][0]["level"] == "error"
    assert "Rust 1.93.0" in doc["runs"][0]["results"][0]["message"]["text"]
    assert "1.96.1" in doc["runs"][0]["results"][0]["message"]["text"]
    assert doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "README.md"


def test_sarif_multiple_drifts():
    result = {
        "toolchain_version": "1.96.1",
        "package_node": "24",
        "drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1", "pos": 10}],
        "rust_drifts": [],
        "node_drifts": [{"file": "CONTRIBUTING.md", "doc_version": "18", "package_version": "24", "pos": 5}],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 2
    rule_ids = {r["id"] for r in rules}
    assert "rust-toolchain-version-drift" in rule_ids
    assert "node-version-drift" in rule_ids
    results = doc["runs"][0]["results"]
    assert len(results) == 2


def test_sarif_informational_warning():
    result = {
        "toolchain_version": None,
        "drifts": [],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [{"file": "README.md", "detail": "Loads font from Google Fonts", "url": "https://fonts.googleapis.com", "pos": 0}],
        "dependabot_drifts": [{"file": ".github/dependabot.yml", "kind": "dependabot_incomplete", "detail": "npm used but not covered", "pos": 0}],
        "lockfile_drifts": [{"file": "package-lock.json", "kind": "lockfile_missing", "detail": "missing package-lock.json", "pos": 0}],
    }
    doc = to_sarif(result)
    results = doc["runs"][0]["results"]
    assert len(results) == 3
    for r in results:
        assert r["level"] == "warning"


def test_sarif_actions_drift():
    result = {
        "toolchain_version": None,
        "drifts": [],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [{"file": ".github/workflows/ci.yml", "action": "actions/checkout", "current": "v4", "suggested": "v5", "pos": 50}],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    assert len(doc["runs"][0]["results"]) == 1
    assert doc["runs"][0]["results"][0]["ruleId"] == "github-actions-node20-deprecated"
    assert doc["runs"][0]["results"][0]["level"] == "error"


def test_sarif_lineending_drift():
    result = {
        "toolchain_version": None,
        "drifts": [],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [{"file": ".gitattributes", "kind": "missing", "detail": "Missing .gitattributes", "pos": 0}],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    assert len(doc["runs"][0]["results"]) == 1
    assert doc["runs"][0]["results"][0]["ruleId"] == "lineending-drift"


def test_sarif_empty_result():
    result = {}
    doc = to_sarif(result)
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def test_sarif_json_roundtrip():
    """SARIF output is valid JSON that can be parsed back."""
    result = {
        "toolchain_version": "1.96.1",
        "drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1", "pos": 10}],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    json_str = json.dumps(doc)
    parsed = json.loads(json_str)
    assert parsed["version"] == "2.1.0"
    assert len(parsed["runs"][0]["results"]) == 1


def test_sarif_multiple_same_rule_dedup():
    """Multiple drifts of same type should only create one rule."""
    result = {
        "toolchain_version": "1.96.1",
        "drifts": [
            {"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1", "pos": 10},
            {"file": "CONTRIBUTING.md", "doc_version": "1.90.0", "toolchain_version": "1.96.1", "pos": 20},
        ],
        "rust_drifts": [],
        "node_drifts": [],
        "bun_drifts": [],
        "python_drifts": [],
        "go_drifts": [],
        "count_drifts": [],
        "actions_drifts": [],
        "lineending_drifts": [],
        "docker_drifts": [],
        "java_drifts": [],
        "maven_drifts": [],
        "terraform_drifts": [],
        "circleci_drifts": [],
        "gitlab_drifts": [],
        "gh_actions_version_drifts": [],
        "k8s_drifts": [],
        "helm_drifts": [],
        "dc_drifts": [],
        "ci_os_drifts": [],
        "dotnet_drifts": [],
        "ruby_drifts": [],
        "php_drifts": [],
        "external_resource_drifts": [],
        "dependabot_drifts": [],
        "lockfile_drifts": [],
    }
    doc = to_sarif(result)
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1
    assert rules[0]["id"] == "rust-toolchain-version-drift"
    assert len(doc["runs"][0]["results"]) == 2
