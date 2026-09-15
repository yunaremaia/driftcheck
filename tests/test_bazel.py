from driftcheck.detector import scan_repo
from driftcheck.detectors.bazel import find_bazel_drift


def put(root, name, text):
    (root / name).write_text(text, encoding="utf-8")


def test_bazelversion_drift(tmp_path):
    put(tmp_path, ".bazelversion", "7.1.0\n")
    put(tmp_path, "README.md", "Requires Bazel 6.5.0")
    drift = find_bazel_drift(tmp_path)
    assert [(d["tool"], d["doc_version"], d["config_version"]) for d in drift] == [
        ("Bazel", "6.5.0", "7.1.0")
    ]


def test_module_bazel_dep_drift(tmp_path):
    put(
        tmp_path,
        "MODULE.bazel",
        'bazel_dep(name = "rules_python", version = "0.35.0")\n',
    )
    put(tmp_path, "README.md", "Use rules_python 0.34.0")
    drift = find_bazel_drift(tmp_path)
    assert drift[0]["source"] == "MODULE.bazel"
    assert drift[0]["config_version"] == "0.35.0"


def test_workspace_http_archive_drift(tmp_path):
    put(
        tmp_path,
        "WORKSPACE.bazel",
        'http_archive(\n name = "rules_go",\n sha256 = "abc",\n urls = ["https://github.com/bazelbuild/rules_go/releases/download/v0.50.1/rules_go-v0.50.1.zip"],\n)\n',
    )
    put(tmp_path, "README.md", "Use rules_go 0.49.0")
    drift = find_bazel_drift(tmp_path)
    assert drift[0]["source"] == "WORKSPACE.bazel"
    assert drift[0]["config_version"] == "0.50.1"


def test_matching_versions_do_not_drift(tmp_path):
    put(tmp_path, ".bazelversion", "7.1.0")
    put(tmp_path, "README.md", "Requires Bazel 7.1.0")
    assert find_bazel_drift(tmp_path) == []


def test_scan_repo_includes_bazel_key(tmp_path):
    put(tmp_path, ".bazelversion", "7.1.0")
    put(tmp_path, "README.md", "Requires Bazel 6.5.0")
    assert scan_repo(tmp_path)["bazel_drifts"][0]["config_version"] == "7.1.0"
