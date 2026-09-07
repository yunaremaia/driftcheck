"""Tests for Elixir drift detection."""
from pathlib import Path
import tempfile
import os

from driftcheck.detectors.elixir import (
    parse_mix_elixir_version,
    find_elixir_drift,
    MIX_ELIXIR_RE,
    ELIXIR_DOC_RE,
)


class TestParseMixElixirVersion:
    def test_basic(self):
        assert parse_mix_elixir_version('elixir: "~> 1.15"') == "1.15"

    def test_with_spaces(self):
        assert parse_mix_elixir_version('elixir:  "~> 1.16"') == "1.16"

    def test_no_match(self):
        assert parse_mix_elixir_version("some other content") is None

    def test_case_insensitive(self):
        assert parse_mix_elixir_version('Elixir: "~> 1.14"') == "1.14"


class TestFindElixirDrift:
    def test_drift_detected(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "This project uses Elixir 1.14."}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "1.14"
        assert result[0]["mix_version"] == "1.15"

    def test_no_drift(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "This project uses Elixir 1.15."}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 0

    def test_no_docs(self):
        mix = 'elixir: "~> 1.15"'
        result = find_elixir_drift(mix, {})
        assert len(result) == 0

    def test_no_mix_version(self):
        mix = "some other content"
        docs = {"README.md": "This project uses Elixir 1.15."}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 0

    def test_multiple_files(self):
        mix = 'elixir: "~> 1.15"'
        docs = {
            "README.md": "This project uses Elixir 1.14.",
            "CONTRIBUTING.md": "Uses Elixir 1.14 too.",
        }
        result = find_elixir_drift(mix, docs)
        assert len(result) == 2

    def test_patch_difference_ignored(self):
        mix = 'elixir: "~> 1.15"'
        docs = {"README.md": "This project uses Elixir 1.15.2."}
        result = find_elixir_drift(mix, docs)
        assert len(result) == 0
