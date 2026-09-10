"""Tests for NVMRC drift detection: .nvmrc vs package.json engines.node."""
from __future__ import annotations
from driftcheck.detectors.nvmrc import (
    parse_nvmrc_version,
    find_nvmrc_drift,
    NVMRC_RE,
    _extract_version,
    _versions_differ,
)


class TestParseNvmrcVersion:
    def test_simple(self):
        assert parse_nvmrc_version("20.12.0") == "20.12.0"

    def test_with_v_prefix(self):
        assert parse_nvmrc_version("v20.12.0") == "20.12.0"

    def test_major_only(self):
        assert parse_nvmrc_version("20") == "20"

    def test_major_minor(self):
        assert parse_nvmrc_version("20.12") == "20.12"

    def test_empty(self):
        assert parse_nvmrc_version("") is None

    def test_whitespace(self):
        assert parse_nvmrc_version("  20.12.0  ") == "20.12.0"

    def test_lts(self):
        # Some .nvmrc files use "lts/*" or similar
        assert parse_nvmrc_version("lts/*") is None


class TestExtractVersion:
    def test_simple(self):
        assert _extract_version("20.12.0") == "20.12.0"

    def test_with_v_prefix(self):
        assert _extract_version("v20.12.0") == "20.12.0"

    def test_with_gte(self):
        assert _extract_version(">=20.12.0") == "20.12.0"

    def test_major_only(self):
        assert _extract_version("20") == "20"


class TestVersionsDiffer:
    def test_same_version(self):
        assert _versions_differ("20.12", "20.12") is False

    def test_different_major(self):
        assert _versions_differ("20.12", "18.12") is True

    def test_different_minor(self):
        assert _versions_differ("20.12", "20.11") is True

    def test_major_only_match(self):
        assert _versions_differ("20", "20.12") is False

    def test_major_only_differ(self):
        assert _versions_differ("20", "18.12") is True

    def test_patch_ignored(self):
        assert _versions_differ("20.12.0", "20.12.5") is False


class TestFindNvmrcDrift:
    def test_drift_vs_package_json(self):
        nvmrc = "20.12.0"
        package_node = "18.12.0"
        result = find_nvmrc_drift(nvmrc, package_node, {})
        assert len(result) == 1
        assert result[0]["nvmrc_version"] == "20.12.0"
        assert result[0]["package_version"] == "18.12.0"

    def test_no_drift_vs_package_json(self):
        nvmrc = "20.12.0"
        package_node = "20.12.0"
        result = find_nvmrc_drift(nvmrc, package_node, {})
        assert result == []

    def test_drift_vs_readme(self):
        nvmrc = "20.12.0"
        docs = {"README.md": "Node.js 18.12.0"}
        result = find_nvmrc_drift(nvmrc, None, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "18.12.0"

    def test_no_drift_vs_readme(self):
        nvmrc = "20.12.0"
        docs = {"README.md": "Node.js 20.12"}
        result = find_nvmrc_drift(nvmrc, None, docs)
        assert result == []

    def test_empty_nvmrc(self):
        result = find_nvmrc_drift("", None, {})
        assert result == []

    def test_no_package_no_docs(self):
        nvmrc = "20.12.0"
        result = find_nvmrc_drift(nvmrc, None, {})
        assert result == []

    def test_major_only_nvmrc(self):
        nvmrc = "20"
        package_node = "18.12.0"
        result = find_nvmrc_drift(nvmrc, package_node, {})
        assert len(result) == 1

    def test_major_only_nvmrc_match(self):
        nvmrc = "20"
        package_node = "20.12.0"
        result = find_nvmrc_drift(nvmrc, package_node, {})
        assert result == []


class TestNvmrcRe:
    def test_match_simple(self):
        m = NVMRC_RE.search("20.12.0")
        assert m is not None
        assert m.group(1) == "20.12.0"

    def test_match_v_prefix(self):
        m = NVMRC_RE.search("v20.12.0")
        assert m is not None
        assert m.group(1) == "20.12.0"

    def test_match_major_only(self):
        m = NVMRC_RE.search("20")
        assert m is not None
        assert m.group(1) == "20"

    def test_no_match(self):
        m = NVMRC_RE.search("lts/*")
        assert m is None
