"""Tests for Terraform drift detector."""
from pathlib import Path

import pytest

from driftcheck.detectors.terraform import (
    parse_terraform_provider_versions,
    find_terraform_drift,
)


class TestParseTerraformProviderVersions:
    def test_single_provider(self):
        text = 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'
        result = parse_terraform_provider_versions(text)
        assert result == {"hashicorp/aws": "5.0"}

    def test_multiple_providers(self):
        text = 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n  google = {\n    source  = "hashicorp/google"\n    version = "4.0"\n  }\n}'
        result = parse_terraform_provider_versions(text)
        assert result == {"hashicorp/aws": "5.0", "hashicorp/google": "4.0"}

    def test_empty(self):
        assert parse_terraform_provider_versions("") == {}


class TestFindTerraformDrift:
    def test_drift_detected(self):
        tf = {"main.tf": 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'}
        docs = {"README.md": "provider \"4.0\""}
        result = find_terraform_drift(tf, docs)
        assert len(result) == 1
        assert result[0]["doc_version"] == "4.0"
        assert result[0]["terraform_version"] == "5.0"

    def test_no_drift(self):
        tf = {"main.tf": 'required_providers {\n  aws = {\n    source  = "hashicorp/aws"\n    version = "5.0"\n  }\n}'}
        docs = {"README.md": "provider \"5.0\""}
        assert find_terraform_drift(tf, docs) == []
