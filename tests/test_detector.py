# ---- PHP/Composer drift tests ----
from driftcheck.detector import find_php_drift, parse_composer_php_version, scan_repo
from driftcheck.detectors.pipfile import find_pipfile_drift
from driftcheck.detectors.conda import find_conda_drift

def test_parse_composer_php_version_basic():
    composer = '{"require": {"php": "^8.2"}}'
    assert parse_composer_php_version(composer) == "8.2"

def test_parse_composer_php_version_range():
    composer = '{"require": {"php": ">=8.1"}}'
    assert parse_composer_php_version(composer) == "8.1"

def test_parse_composer_php_version_tilde():
    composer = '{"require": {"php": "~8.3.0"}}'
    assert parse_composer_php_version(composer) == "8.3"

def test_parse_composer_php_version_missing():
    composer = '{"require": {"ext-json": "*"}}'
    assert parse_composer_php_version(composer) is None

def test_php_no_drift():
    composer = '{"require": {"php": "^8.2"}}'
    docs = {"README.md": "Requires PHP 8.2+"}
    assert find_php_drift(composer, docs) == []

def test_php_detects_drift():
    composer = '{"require": {"php": "^8.2"}}'
    docs = {"README.md": "Requires PHP 8.1"}
    drifts = find_php_drift(composer, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "8.1"
    assert drifts[0]["composer_version"] == "8.2"

def test_php_no_composer_returns_empty():
    assert find_php_drift("", {"README.md": "PHP 8.2"}) == []

def test_php_drift_included_in_scan():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "composer.json").write_text('{"require": {"php": "^8.3"}}')
        (root / "README.md").write_text("Requires PHP 8.2 to run")
        result = scan_repo(root)
        assert "php_drifts" in result
        assert len(result["php_drifts"]) == 1

def test_php_drift_skips_toc_numbered():
    composer = '{"require": {"php": "^8.2"}}'
    docs = {"README.md": "1. PHP 8.1 stuff\n2. PHP 8.2 stuff"}
    assert find_php_drift(composer, docs) == []

def test_php_drift_same_major_minor():
    # composer has 8.2, README says 8.2.5 — same major.minor, no drift
    composer = '{"require": {"php": "^8.2"}}'
    docs = {"README.md": "PHP 8.2.5 required"}
    assert find_php_drift(composer, docs) == []


# ---- Bun drift tests ----
from driftcheck.detector import find_bun_drift, parse_bun_version_from_package, scan_repo

def test_parse_bun_version_basic():
    pkg = '{"engines": {"bun": ">=1.0"}}'
    assert parse_bun_version_from_package(pkg) == "1.0"

def test_parse_bun_version_caret():
    pkg = '{"engines": {"bun": "^1.2.0"}}'
    assert parse_bun_version_from_package(pkg) == "1.2"

def test_parse_bun_version_missing():
    pkg = '{"engines": {"node": "24.x"}}'
    assert parse_bun_version_from_package(pkg) is None

def test_bun_no_drift():
    pkg = '{"engines": {"bun": ">=1.2"}}'
    docs = {"README.md": "Requires Bun 1.2"}
    assert find_bun_drift(pkg, docs) == []

def test_bun_detects_drift():
    pkg = '{"engines": {"bun": ">=1.2"}}'
    docs = {"README.md": "Requires Bun 1.0"}
    drifts = find_bun_drift(pkg, docs)
    assert len(drifts) == 1
    assert drifts[0]["doc_version"] == "1.0"
    assert drifts[0]["package_version"] == "1.2"

def test_bun_no_package_returns_empty():
    assert find_bun_drift("", {"README.md": "Bun 1.0"}) == []

def test_bun_drift_included_in_scan():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"engines": {"bun": "^1.3"}}')
        (root / "README.md").write_text("Requires Bun 1.2")
        result = scan_repo(root)
        assert "bun_drifts" in result
        assert len(result["bun_drifts"]) == 1

def test_bun_drift_skips_toc_numbered():
    pkg = '{"engines": {"bun": ">=1.2"}}'
    docs = {"README.md": "1. Bun 1.0 stuff\n2. Bun 1.2 stuff"}
    assert find_bun_drift(pkg, docs) == []

def test_bun_drift_same_major_minor():
    # package has 1.2, README says 1.2.5 — same major.minor, no drift
    pkg = '{"engines": {"bun": ">=1.2"}}'
    docs = {"README.md": "Bun 1.2.5 required"}
    assert find_bun_drift(pkg, docs) == []


# ---- Lockfile drift tests ----
from driftcheck.detector import find_lockfile_drift

def test_lockfile_missing_npm():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"dependencies": {}}')
        drifts = find_lockfile_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "lockfile_missing"
        assert "package-lock.json" in drifts[0]["file"]

def test_lockfile_missing_cargo():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"')
        drifts = find_lockfile_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "lockfile_missing"
        assert "Cargo.lock" in drifts[0]["file"]

def test_lockfile_missing_go():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "go.mod").write_text("module test\ngo 1.23")
        drifts = find_lockfile_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "lockfile_missing"
        assert "go.sum" in drifts[0]["file"]

def test_lockfile_no_drift():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"dependencies": {}}')
        (root / "package-lock.json").write_text('{"name": "test"}')
        drifts = find_lockfile_drift(root)
        assert len(drifts) == 0

def test_lockfile_orphaned():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package-lock.json").write_text('{"name": "test"}')
        drifts = find_lockfile_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["kind"] == "lockfile_orphaned"

def test_lockfile_drift_included_in_scan():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "package.json").write_text('{"dependencies": {}}')
        result = scan_repo(root)
        assert "lockfile_drifts" in result
        assert len(result["lockfile_drifts"]) == 1


class TestPipfileDrift:
    """Tests for Pipfile vs Pipfile.lock drift detection."""

    def test_pipfile_drift_detected(self, tmp_path):
        """Test drift when Pipfile.lock has different version."""
        pipfile = tmp_path / "Pipfile"
        pipfile.write_text("""
[packages]
flask = "==2.0.0"
requests = ">=2.28.0"
""")
        pipfile_lock = tmp_path / "Pipfile.lock"
        pipfile_lock.write_text(
            '{"default": {"flask": {"version": "==2.0.1"}, '
            '"requests": {"version": "==2.28.0"}}}'
        )
        drifts = find_pipfile_drift(tmp_path)
        assert len(drifts) >= 1
        assert drifts[0]["package"] == "flask"

    def test_pipfile_no_drift(self, tmp_path):
        """Test no drift when versions match."""
        pipfile = tmp_path / "Pipfile"
        pipfile.write_text("""
[packages]
flask = "==2.0.0"
""")
        pipfile_lock = tmp_path / "Pipfile.lock"
        pipfile_lock.write_text(
            '{"default": {"flask": {"version": "==2.0.0"}}}'
        )
        drifts = find_pipfile_drift(tmp_path)
        assert len(drifts) == 0

    def test_pipfile_missing(self, tmp_path):
        """Test no drift when Pipfile doesn't exist."""
        drifts = find_pipfile_drift(tmp_path)
        assert len(drifts) == 0


class TestCondaDrift:
    """Tests for Conda environment.yml drift detection."""

    def test_conda_unpinned_detected(self, tmp_path):
        """Test drift for unpinned packages."""
        env = tmp_path / "environment.yml"
        env.write_text("""
name: test
dependencies:
  - python=3.11
  - numpy
  - pandas>=1.5
""")
        drifts = find_conda_drift(tmp_path)
        # numpy is unpinned
        assert any(d["package"] == "numpy" for d in drifts)

    def test_conda_no_drift(self, tmp_path):
        """Test no drift when all packages are pinned."""
        env = tmp_path / "environment.yml"
        env.write_text("""
name: test
dependencies:
  - python=3.11
  - numpy=1.24.0
  - pandas=2.0.0
""")
        drifts = find_conda_drift(tmp_path)
        assert len(drifts) == 0

    def test_conda_missing(self, tmp_path):
        """Test no drift when environment.yml doesn't exist."""
        drifts = find_conda_drift(tmp_path)
        assert len(drifts) == 0

