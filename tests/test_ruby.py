"""Tests for Ruby drift detection: Gemfile ruby version vs README mentions."""
from __future__ import annotations
from driftcheck.detectors.ruby import (
    parse_gemfile_ruby_version,
    find_ruby_drift,
    GEMFILE_RUBY_RE,
    RUBY_DOC_RE,
)


class TestParseGemfileRubyVersion:
    def test_standard(self):
        text = "ruby '3.2.0'"
        assert parse_gemfile_ruby_version(text) == "3.2.0"

    def test_double_quotes(self):
        text = 'ruby "3.2.0"'
        assert parse_gemfile_ruby_version(text) == "3.2.0"

    def test_major_minor(self):
        text = "ruby '3.2'"
        assert parse_gemfile_ruby_version(text) == "3.2"

    def test_empty(self):
        assert parse_gemfile_ruby_version("") is None

    def test_no_ruby_line(self):
        text = "source 'https://rubygems.org'"
        assert parse_gemfile_ruby_version(text) is None

    def test_ruby_with_comment(self):
        text = "ruby '3.2.0' # comment"
        assert parse_gemfile_ruby_version(text) == "3.2.0"


class TestFindRubyDrift:
    def test_drift_detected(self):
        gemfile = "ruby '3.2.0'"
        docs = {"README.md": "Requires Ruby 3.1"}
        result = find_ruby_drift(gemfile, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "3.1"
        assert result[0]["gemfile_version"] == "3.2.0"

    def test_no_drift(self):
        gemfile = "ruby '3.2.0'"
        docs = {"README.md": "Requires Ruby 3.2"}
        assert find_ruby_drift(gemfile, docs) == []

    def test_empty_gemfile(self):
        assert find_ruby_drift("", {"README.md": "Ruby 3.2"}) == []

    def test_no_ruby_in_docs(self):
        gemfile = "ruby '3.2.0'"
        docs = {"README.md": "Some project"}
        assert find_ruby_drift(gemfile, docs) == []

    def test_drift_major(self):
        gemfile = "ruby '3.0.0'"
        docs = {"README.md": "Requires Ruby 2.7"}
        result = find_ruby_drift(gemfile, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "2.7"

    def test_multiple_docs(self):
        gemfile = "ruby '3.2.0'"
        docs = {
            "README.md": "Ruby 3.2",
            "CONTRIBUTING.md": "Ruby 3.1 required",
        }
        result = find_ruby_drift(gemfile, docs)
        assert len(result) == 1
        assert result[0]["file"] == "CONTRIBUTING.md"

    def test_case_insensitive(self):
        gemfile = "ruby '3.2.0'"
        docs = {"README.md": "requires ruby 3.1"}
        result = find_ruby_drift(gemfile, docs)
        assert len(result) == 1

    def test_empty_docs(self):
        gemfile = "ruby '3.2.0'"
        assert find_ruby_drift(gemfile, {}) == []


class TestGemfileRubyRe:
    def test_match_single_quotes(self):
        m = GEMFILE_RUBY_RE.search("ruby '3.2.0'")
        assert m is not None
        assert m.group("ver") == "3.2.0"

    def test_match_double_quotes(self):
        m = GEMFILE_RUBY_RE.search('ruby "3.2.0"')
        assert m is not None

    def test_no_match(self):
        m = GEMFILE_RUBY_RE.search("source 'https://rubygems.org'")
        assert m is None


class TestRubyDocRe:
    def test_match_install(self):
        m = RUBY_DOC_RE.search("Install Ruby 3.2")
        assert m is not None
        assert m.group("ver") == "3.2"

    def test_match_requires(self):
        m = RUBY_DOC_RE.search("Requires Ruby 3.1")
        assert m is not None

    def test_match_bare(self):
        m = RUBY_DOC_RE.search("Ruby 3.2")
        assert m is not None
        assert m.group("ver2") == "3.2"

    def test_no_match(self):
        m = RUBY_DOC_RE.search("Some text")
        assert m is None
