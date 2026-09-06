# ---- PHP/Composer drift tests ----
from driftcheck.detector import find_php_drift, parse_composer_php_version, scan_repo

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
