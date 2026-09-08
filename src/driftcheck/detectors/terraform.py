"""Terraform drift detection: versions.tf provider versions vs README."""
from __future__ import annotations
import re

TERRAFORM_PROVIDER_RE = re.compile(r'source\s*=\s*"(?P<source>[^"]+)"[^}]*version\s*=\s*"(?P<ver>[^"]+)"', re.S)
TERRAFORM_VER_RE = re.compile(r'(?:provider|terraform|version)\s+"?(?P<ver>\d+\.\d+(?:\.\d+)?)"?', re.I)


def parse_terraform_provider_versions(text: str) -> dict[str, str]:
    """Return {source: version} map of required_providers in versions.tf."""
    result = {}
    for m in TERRAFORM_PROVIDER_RE.finditer(text):
        result[m.group("source")] = m.group("ver")
    return result


def find_terraform_drift(terraform_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Terraform provider versions and README mentions."""
    all_providers: dict[str, str] = {}
    for fname, content in terraform_files.items():
        for source, ver in parse_terraform_provider_versions(content).items():
            all_providers[source] = ver

    if not all_providers:
        return []

    drifts = []
    for fname, content in docs.items():
        for m in TERRAFORM_VER_RE.finditer(content):
            ver = m.group("ver")
            # Check if this version matches any provider version
            for source, tf_ver in all_providers.items():
                if ver != tf_ver and ver.split(".")[:2] == tf_ver.split(".")[:2]:
                    # Same major.minor, different patch — skip
                    continue
                if ver != tf_ver:
                    drifts.append({
                        "file": fname,
                        "doc_version": ver,
                        "terraform_version": tf_ver,
                        "provider": source,
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
