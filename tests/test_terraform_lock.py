"""Tests for Terraform lockfile vs required_providers constraints."""
from driftcheck.detectors.terraform_lock import (
    find_terraform_lock_drift,
    parse_lock_versions,
    parse_required_providers,
)


TF = """
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 3.0.0"
    }
  }
}
"""

LOCK = """
provider "registry.terraform.io/hashicorp/aws" {
  version = "5.45.0"
}
provider "registry.terraform.io/hashicorp/azurerm" {
  version = "3.1.0"
}
"""


def test_parse_providers_and_lock():
    assert parse_required_providers(TF)["hashicorp/aws"] == "~> 5.0"
    locked = parse_lock_versions(LOCK)
    assert locked["hashicorp/aws"] == "5.45.0"
    assert locked["hashicorp/azurerm"] == "3.1.0"


def test_pessimistic_match_and_exact_mismatch():
    drifts = find_terraform_lock_drift({"versions.tf": TF}, LOCK)
    assert len(drifts) == 1
    assert drifts[0]["provider"] == "hashicorp/azurerm"
    assert drifts[0]["lock_version"] == "3.1.0"


def test_satisfying_lock_is_quiet():
    lock = LOCK.replace("3.1.0", "3.0.0")
    assert find_terraform_lock_drift({"main.tf": TF}, lock) == []


def test_missing_lock_is_quiet():
    assert find_terraform_lock_drift({"main.tf": TF}, "") == []


def test_scan_repo_terraform_lock(tmp_path):
    from driftcheck.detector import scan_repo

    (tmp_path / "versions.tf").write_text(
        """
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.0.0"
    }
  }
}
""",
        encoding="utf-8",
    )
    (tmp_path / ".terraform.lock.hcl").write_text(
        """
provider "registry.terraform.io/hashicorp/aws" {
  version = "5.1.0"
}
""",
        encoding="utf-8",
    )
    result = scan_repo(tmp_path)
    assert any(item["provider"] == "hashicorp/aws" for item in result["terraform_lock_drifts"])
