"""TDD for driftcheck — RED first, then GREEN."""
import tempfile
from pathlib import Path

from driftcheck.detector import find_rust_drift, scan_repo, apply_fixes

def test_no_drift():
    toolchain = 'channel = "1.96.1"'
    docs = {"README.md": "Install Rust 1.96.1", "docs/README.zh-CN.md": "Rust 1.96.1"}
    assert find_rust_drift(toolchain, docs) == []

def test_detects_drift():
    toolchain = 'channel = "1.96.1"'
    docs = {"README.md": "Install Rust 1.93.0", "docs/README.de.md": "Rust 1.96.1"}
    drifts = find_rust_drift(toolchain, docs)
    assert len(drifts) == 1
    assert drifts[0]["file"] == "README.md"
    assert drifts[0]["doc_version"] == "1.93.0"
    assert drifts[0]["toolchain_version"] == "1.96.1"

def test_no_toolchain_returns_empty():
    assert find_rust_drift("", {"README.md": "Rust 1.93.0"}) == []

from driftcheck.detector import parse_cargo_rust_version, find_rust_drift_multi

def test_cargo_rust_version_parse():
    assert parse_cargo_rust_version('rust-version = "1.96.1"\n') == "1.96.1"
    assert parse_cargo_rust_version('rust-version = "1.96"\n') == "1.96"
    assert parse_cargo_rust_version('[package]\nversion = "0.1"\n') is None

def test_rust_drift_multi_cargo_source():
    cargo = 'rust-version = "1.96.1"\n'
    docs = {"README.md": "Build with Rust 1.90.0"}
    drifts = find_rust_drift_multi(toolchain_text="", cargo_text=cargo, docs=docs)
    assert len(drifts) == 1
    assert drifts[0]["cargo_version"] == "1.96.1"

def test_rust_drift_multi_channel_without_patch():
    toolchain = 'channel = "1.96"\n'
    docs = {"README.md": "Rust 1.96.1"}
    assert find_rust_drift_multi(toolchain_text=toolchain, cargo_text="", docs=docs) == []

def test_rust_drift_multi_minor_mismatch():
    toolchain = 'channel = "1.96"\n'
    docs = {"README.md": "Rust 1.90 required"}
    drifts = find_rust_drift_multi(toolchain_text=toolchain, cargo_text="", docs=docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "1.90"


def test_scan_repo():
    from pathlib import Path
    import tempfile
    from driftcheck.detector import scan_repo
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "rust-toolchain.toml").write_text('channel = "1.96.1"')
        (root / "README.md").write_text("Install Rust 1.93.0")
        result = scan_repo(root)
        assert result["toolchain_version"] == "1.96.1"
        assert len(result["drifts"]) == 1


from driftcheck.detector import find_node_drift

def test_node_no_drift():
    pkg = '{"engines": {"node": "24.x"}}'
    docs = {"README.md": "Install Node.js 24"}
    assert find_node_drift(pkg, docs) == []

def test_node_detects_drift():
    pkg = '{"engines": {"node": "24.x"}}'
    docs = {"README.md": "Install Node.js 18"}
    drifts = find_node_drift(pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "18"
    assert drifts[0]["package_version"] == "24"


from driftcheck.detector import find_python_drift

def test_python_no_drift():
    pkg = 'requires-python = ">=3.10"'
    docs = {"README.md": "Python 3.10+"}
    assert find_python_drift(pkg, docs) == []

def test_python_detects_drift():
    pkg = 'requires-python = ">=3.12"'
    docs = {"README.md": "Python 3.10+"}
    drifts = find_python_drift(pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "3.10"
    assert drifts[0]["pyproject_version"] == "3.12"

def test_python_no_drift_when_doc_above_floor():
    # requires-python is a floor; a README mentioning a higher version
    # (e.g. an example using 3.12 while requires-python is >=3.8) is fine.
    pkg = 'requires-python = ">=3.8"'
    docs = {"README.md": "uv python install 3.12 3.13 3.14"}
    assert find_python_drift(pkg, docs) == []


from driftcheck.detector import find_go_drift, parse_go_version_from_gomod

def test_go_no_drift():
    gomod = "module example.com/foo\n\ngo 1.23\n"
    docs = {"README.md": "Requires Go 1.23"}
    assert find_go_drift(gomod, docs) == []

def test_go_detects_drift():
    gomod = "module example.com/foo\n\ngo 1.23\n"
    docs = {"README.md": "Requires Go 1.21"}
    drifts = find_go_drift(gomod, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "1.21"
    assert drifts[0]["gomod_version"] == "1.23"

def test_parse_go_version_from_gomod_missing():
    assert parse_go_version_from_gomod("module foo\n") is None


from driftcheck.detector import apply_fixes

def test_apply_fixes_rewrites_doc_to_match_toolchain():
    from pathlib import Path
    import tempfile
    result = {
        "drifts": [{"file": "README.md", "doc_version": "1.93.0", "toolchain_version": "1.96.1"}],
        "node_drifts": [{"file": "CONTRIBUTING.md", "doc_version": "18", "package_version": "24"}],
        "python_drifts": [{"file": "docs/README.md", "doc_version": "3.10", "pyproject_version": "3.12"}],
        "go_drifts": [{"file": "README.md", "doc_version": "1.21", "gomod_version": "1.23"}],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("Rust 1.93.0 and Go 1.21 here")
        (root / "CONTRIBUTING.md").write_text("Use Node.js 18 please")
        (root / "docs").mkdir()
        (root / "docs" / "README.md").write_text("Python 3.10 required")
        fixed = apply_fixes(root, result)
        assert set(fixed) == {"README.md", "CONTRIBUTING.md", "docs/README.md"}
        assert "Rust 1.96.1" in (root / "README.md").read_text()
        assert "Go 1.23" in (root / "README.md").read_text()
        assert "Node.js 24" in (root / "CONTRIBUTING.md").read_text()
        assert "Python 3.12" in (root / "docs" / "README.md").read_text()


def test_apply_fixes_idempotent_when_no_drift():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("Rust 1.96.1")
        fixed = apply_fixes(root, {"drifts": [], "node_drifts": [], "python_drifts": [], "go_drifts": []})
        assert fixed == []


def test_lineending_drift_detected_when_missing():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("project")
        r = scan_repo(root)
        assert r["lineending_drifts"], "expected a lineending drift when .gitattributes is absent"
        assert r["lineending_drifts"][0]["file"] == ".gitattributes"


def test_lineending_drift_apply_fix_creates_gitattributes():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("project")
        r = scan_repo(root)
        fixed = apply_fixes(root, r)
        assert ".gitattributes" in fixed
        assert "text=auto eol=lf" in (root / ".gitattributes").read_text()
        # re-scan should be clean
        assert scan_repo(root)["lineending_drifts"] == []


def test_lineending_drift_absent_when_present():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("project")
        (root / ".gitattributes").write_text("* text=auto eol=lf\n")
        r = scan_repo(root)
        assert r["lineending_drifts"] == []

from driftcheck.detector import find_count_drift

def test_count_no_drift():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "skills").mkdir()
        for name in ["a", "b", "c"]:
            (root / "skills" / name).mkdir()
        docs = {"README.md": "We have 3 skills in total"}
        assert find_count_drift(root, docs) == []

def test_count_detects_drift():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "skills").mkdir()
        for name in ["a", "b", "c"]:
            (root / "skills" / name).mkdir()
        docs = {"README.md": "We have 161 skills but also 3 skills"}
        drifts = find_count_drift(root, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_count"] == "161"
        assert drifts[0]["actual_count"] == 3

def test_count_no_skills_dir_returns_empty():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = {"README.md": "We have 161 skills"}
        assert find_count_drift(root, docs) == []

def test_count_fix_rewrites():
    from driftcheck.detector import apply_fixes
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "skills").mkdir()
        for n in ["a", "b"]:
            (root / "skills" / n).mkdir()
        (root / "README.md").write_text("Our project has 161 skills")
        result = {"count_drifts": [{"file": "README.md", "doc_count": "161", "actual_count": 2}]}
        fixed = apply_fixes(root, result)
        assert "README.md" in fixed
        assert "2 skills" in (root / "README.md").read_text()

from driftcheck.detector import find_actions_node_drift

def test_actions_no_drift_when_fixed():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v5\n  - uses: actions/setup-node@v5\n")
        assert find_actions_node_drift(root) == []

def test_actions_detects_node20():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v4\n  - uses: actions/configure-pages@v5\n  - uses: pnpm/action-setup@v4\n")
        drifts = find_actions_node_drift(root)
        assert len(drifts) == 3
        assert {d["action"] for d in drifts} == {"actions/checkout", "actions/configure-pages", "pnpm/action-setup"}
        assert drifts[0]["suggested"] == "v5"
        # configure-pages v5 -> v6
        assert [d for d in drifts if d["action"]=="actions/configure-pages"][0]["suggested"]=="v6"

def test_actions_fix_rewrites():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v4\n")
        result = {"actions_drifts": [{"file": ".github/workflows/ci.yml", "action": "actions/checkout", "current": "v4", "suggested": "v5"}]}
        from driftcheck.detector import apply_fixes
        fixed = apply_fixes(root, result)
        assert ".github/workflows/ci.yml" in fixed
        assert "actions/checkout@v5" in (root / ".github" / "workflows" / "ci.yml").read_text()

def test_actions_no_workflows_returns_empty():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        assert find_actions_node_drift(root) == []

from driftcheck.detector import find_external_resource_drift

def test_external_resource_detects_google_fonts():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "archify" / "assets").mkdir(parents=True)
        (root / "archify" / "assets" / "template.html").write_text('<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono">')
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["host"] == "fonts.googleapis.com"
        assert "archify#242" in drifts[0]["detail"]

def test_external_resource_no_false_positive():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "archify" / "assets").mkdir(parents=True)
        (root / "archify" / "assets" / "template.html").write_text("<style>body{font:system}</style>")
        assert find_external_resource_drift(root) == []

def test_external_resource_no_template_returns_empty():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        assert find_external_resource_drift(root) == []

def test_external_resource_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "archify" / "assets").mkdir(parents=True)
        (root / "archify" / "assets" / "template.html").write_text('<link href="https://fonts.googleapis.com/css">')
        result = scan_repo(root)
        assert "external_resource_drifts" in result
        assert len(result["external_resource_drifts"]) == 1

def test_python_drift_skips_cpython_stack():
    # CPython 3.11 compatibility stack is not a repo requirement
    docs = {"README.md": "PyTDC 1.1.15 on its verified CPython 3.11 compatibility stack"}
    assert find_python_drift('requires-python = ">=3.13"', docs) == []

def test_python_drift_still_catches_real_requirement():
    docs = {"README.md": "Requires Python 3.11 for install"}
    drifts = find_python_drift('requires-python = ">=3.13"', docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "3.11"

def test_count_drift_skips_subset_ship():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "skills").mkdir()
        for i in range(163):
            (root / f"skills/s{i}").mkdir()
        # 32 is subset (ships X), 163 is total — should not drift
        docs = {"CONTRIBUTING.md": "32 skills ship a scripts/_common.py, 163 skills total"}
        assert find_count_drift(root, docs) == []

def test_count_drift_still_catches_wrong_total():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "skills").mkdir()
        for i in range(163):
            (root / f"skills/s{i}").mkdir()
        docs = {"README.md": "We have 32 skills total"}
        drifts = find_count_drift(root, docs)
        assert len(drifts) == 1
        assert drifts[0]["doc_count"] == "32"


# ---- Docker drift tests ----
from driftcheck.detector import find_docker_drift, parse_dockerfile_from

def test_parse_dockerfile_from_basic():
    df = "FROM node:24-slim\nWORKDIR /app\nCOPY . ."
    result = parse_dockerfile_from(df)
    assert result == {"node": "24-slim"}

def test_parse_dockerfile_from_multi_stage():
    df = "FROM golang:1.23 AS builder\nRUN go build\nFROM alpine:3.21\nCOPY --from=builder /app ."
    result = parse_dockerfile_from(df)
    assert result == {"golang": "1.23", "alpine": "3.21"}

def test_docker_no_drift():
    dockerfiles = {"Dockerfile": "FROM node:24-slim"}
    docs = {"README.md": "Docker node:24 image"}
    assert find_docker_drift(dockerfiles, docs) == []

def test_docker_detects_drift():
    dockerfiles = {"Dockerfile": "FROM node:24-slim"}
    docs = {"README.md": "Docker node:22 image"}
    drifts = find_docker_drift(dockerfiles, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_image"] == "node:22"
    assert drifts[0]["dockerfile_image"] == "node:24-slim"

def test_docker_no_dockerfile_returns_empty():
    assert find_docker_drift({}, {"README.md": "node:22"}) == []

def test_docker_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Dockerfile").write_text("FROM python:3.12-slim")
        (root / "README.md").write_text("Docker python:3.11 base image")
        result = scan_repo(root)
        assert "docker_drifts" in result
        assert len(result["docker_drifts"]) == 1


# ---- Java/Gradle drift tests ----
from driftcheck.detector import find_java_drift, parse_gradle_java_version

def test_parse_gradle_source_compatibility():
    gradle = "sourceCompatibility = '17'\n"
    assert parse_gradle_java_version(gradle) == "17"

def test_parse_gradle_jvm_target():
    gradle = 'jvmTarget = "21"\n'
    assert parse_gradle_java_version(gradle) == "21"

def test_parse_gradle_java_version_enum():
    gradle = "sourceCompatibility = JavaVersion.VERSION_21\n"
    assert parse_gradle_java_version(gradle) == "21"

def test_parse_gradle_no_java_info():
    gradle = "plugins { id 'java' }\n"
    assert parse_gradle_java_version(gradle) is None

def test_java_no_drift():
    gradle = "sourceCompatibility = '17'"
    docs = {"README.md": "Requires Java 17"}
    assert find_java_drift(gradle, docs) == []

def test_java_detects_drift():
    gradle = "sourceCompatibility = '17'"
    docs = {"README.md": "Requires Java 11"}
    drifts = find_java_drift(gradle, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "11"
    assert drifts[0]["gradle_version"] == "17"

def test_java_no_gradle_returns_empty():
    assert find_java_drift("", {"README.md": "Java 17"}) == []


# ---- Maven drift tests ----
from driftcheck.detector import find_maven_drift, parse_maven_java_version

def test_parse_maven_java_version():
    pom = "<java.version>17</java.version>"
    assert parse_maven_java_version(pom) == "17"

def test_parse_maven_compiler_source():
    pom = "<maven.compiler.source>21</maven.compiler.source>"
    assert parse_maven_java_version(pom) == "21"

def test_parse_maven_no_java_info():
    pom = "<project><groupId>com.example</groupId></project>"
    assert parse_maven_java_version(pom) is None

def test_maven_no_drift():
    pom = "<java.version>17</java.version>"
    docs = {"README.md": "Requires Java 17"}
    assert find_maven_drift(pom, docs) == []

def test_maven_detects_drift():
    pom = "<java.version>17</java.version>"
    docs = {"README.md": "Requires Java 11"}
    drifts = find_maven_drift(pom, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "11"
    assert drifts[0]["maven_version"] == "17"

def test_maven_no_pom_returns_empty():
    assert find_maven_drift("", {"README.md": "Java 17"}) == []

def test_maven_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pom.xml").write_text("<java.version>21</java.version>")
        (root / "README.md").write_text("Requires Java 17 to build")
        result = scan_repo(root)
        assert "maven_drifts" in result
        assert len(result["maven_drifts"]) == 1

def test_java_drift_included_in_scan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "build.gradle").write_text("sourceCompatibility = '21'\n")
        (root / "README.md").write_text("Requires Java 17 to build")
        result = scan_repo(root)
        assert "java_drifts" in result
        assert len(result["java_drifts"]) == 1

