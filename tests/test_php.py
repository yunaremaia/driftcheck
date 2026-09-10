"""Tests for PHP/Composer drift detection: composer.json require.php vs README."""
from __future__ import annotations
from driftcheck.detectors.php import (
    parse_composer_php_version,
    find_php_drift,
    COMPOSER_PHP_RE,
    PHP_DOC_RE,
)


class TestParseComposerPhpVersion:
    def test_caret_range(self):
        text = '{"require": {"php": "^8.2"}}'
        assert parse_composer_php_version(text) == "8.2"

    def test_gte_range(self):
        text = '{"require": {"php": ">=8.1"}}'
        assert parse_composer_php_version(text) == "8.1"

    def test_tilde_range(self):
        text = '{"require": {"php": "~8.2"}}'
        assert parse_composer_php_version(text) == "8.2"

    def test_exact_version(self):
        text = '{"require": {"php": "8.2.0"}}'
        assert parse_composer_php_version(text) == "8.2"

    def test_wildcard(self):
        text = '{"require": {"php": "8.2.*"}}'
        assert parse_composer_php_version(text) == "8.2"

    def test_empty(self):
        assert parse_composer_php_version("") is None

    def test_no_php_requirement(self):
        text = '{"require": {"laravel/framework": "^10.0"}}'
        assert parse_composer_php_version(text) is None

    def test_complex_range(self):
        text = '{"require": {"php": ">=8.1 <8.3"}}'
        # Should extract the first version
        result = parse_composer_php_version(text)
        assert result is not None


class TestFindPhpDrift:
    def test_drift_detected(self):
        composer = '{"require": {"php": "^8.2"}}'
        docs = {"README.md": "Requires PHP 8.1"}
        result = find_php_drift(composer, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "8.1"
        assert result[0]["composer_version"] == "8.2"

    def test_no_drift(self):
        composer = '{"require": {"php": "^8.2"}}'
        docs = {"README.md": "Requires PHP 8.2"}
        assert find_php_drift(composer, docs) == []

    def test_empty_composer(self):
        assert find_php_drift("", {"README.md": "PHP 8.2"}) == []

    def test_no_php_in_docs(self):
        composer = '{"require": {"php": "^8.2"}}'
        docs = {"README.md": "Some project"}
        assert find_php_drift(composer, docs) == []

    def test_drift_major(self):
        composer = '{"require": {"php": "^8.0"}}'
        docs = {"README.md": "Requires PHP 7.4"}
        result = find_php_drift(composer, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "7.4"

    def test_multiple_docs(self):
        composer = '{"require": {"php": "^8.2"}}'
        docs = {
            "README.md": "PHP 8.2",
            "CONTRIBUTING.md": "PHP 8.1 required",
        }
        result = find_php_drift(composer, docs)
        assert len(result) == 1
        assert result[0]["file"] == "CONTRIBUTING.md"

    def test_case_insensitive(self):
        composer = '{"require": {"php": "^8.2"}}'
        docs = {"README.md": "requires php 8.1"}
        result = find_php_drift(composer, docs)
        assert len(result) == 1

    def test_empty_docs(self):
        composer = '{"require": {"php": "^8.2"}}'
        assert find_php_drift(composer, docs={}) == []


class TestComposerPhpRe:
    def test_match_caret(self):
        m = COMPOSER_PHP_RE.search('"php": "^8.2"')
        assert m is not None
        assert m.group("ver") == "^8.2"

    def test_match_gte(self):
        m = COMPOSER_PHP_RE.search('"php": ">=8.1"')
        assert m is not None

    def test_no_match(self):
        m = COMPOSER_PHP_RE.search('"laravel": "^10.0"')
        assert m is None


class TestPhpDocRe:
    def test_match_requires(self):
        m = PHP_DOC_RE.search("Requires PHP 8.2")
        assert m is not None
        assert m.group("ver") == "8.2"

    def test_match_minimum(self):
        m = PHP_DOC_RE.search("Minimum PHP 8.1")
        assert m is not None

    def test_match_bare(self):
        m = PHP_DOC_RE.search("PHP 8.2")
        assert m is not None
        assert m.group("ver2") == "8.2"

    def test_no_match(self):
        m = PHP_DOC_RE.search("Some text")
        assert m is None
