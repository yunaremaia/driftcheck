"""Version file drift detection: .ruby-version, .python-version, .node-version, .java-version, .terraform-version.

Detects drift between version manager files (rbenv, pyenv, nodenv, jenv, tfenv)
and README mentions.
"""
from __future__ import annotations
import re

# Match version mentions in README
VERSION_RE = re.compile(
    r'(?:ruby|python|node\.js|nodejs|node|java|terraform|tf)\s*[:=]?\s*(?P<version>\d[\d.]*)',
    re.I,
)


def parse_ruby_version(text: str) -> str | None:
    """Return version from .ruby-version file."""
    text = text.strip()
    if text and not text.startswith("#"):
        return text.split()[0] if text.split() else None
    return None


def parse_python_version(text: str) -> str | None:
    """Return version from .python-version file."""
    text = text.strip()
    if text and not text.startswith("#"):
        return text.split()[0] if text.split() else None
    return None


def parse_node_version(text: str) -> str | None:
    """Return version from .node-version file."""
    text = text.strip()
    if text and not text.startswith("#"):
        return text.split()[0] if text.split() else None
    return None


def parse_java_version(text: str) -> str | None:
    """Return version from .java-version file."""
    text = text.strip()
    if text and not text.startswith("#"):
        return text.split()[0] if text.split() else None
    return None


def parse_terraform_version(text: str) -> str | None:
    """Return version from .terraform-version file."""
    text = text.strip()
    if text and not text.startswith("#"):
        return text.split()[0] if text.split() else None
    return None


def find_version_file_drift(
    version_files: dict[str, str],
    docs: dict[str, str],
    tool_name: str,
) -> list[dict]:
    """Detect drift between version file declarations and README mentions."""
    all_versions: dict[str, str] = {}
    for fname, content in version_files.items():
        version = None
        if ".ruby-version" in fname:
            version = parse_ruby_version(content)
        elif ".python-version" in fname:
            version = parse_python_version(content)
        elif ".node-version" in fname:
            version = parse_node_version(content)
        elif ".java-version" in fname:
            version = parse_java_version(content)
        elif ".terraform-version" in fname:
            version = parse_terraform_version(content)
        if version:
            all_versions[fname] = version

    if not all_versions:
        return []

    drifts = []
    for fname, version in all_versions.items():
        for doc_fname, doc_content in docs.items():
            for m in VERSION_RE.finditer(doc_content):
                doc_ver = m.group("version")
                tool = m.group(0).split()[0].lower()
                if _tool_matches(tool, tool_name) and not _versions_match(doc_ver, version):
                    drifts.append({
                        "file": doc_fname,
                        "tool": tool_name,
                        "doc_version": doc_ver,
                        "version_file": version,
                        "pos": m.start(),
                    })
                    break  # one drift per doc file
            if any(d["file"] == doc_fname for d in drifts):
                break  # stop checking more docs for this version file

    return drifts


def _tool_matches(tool: str, tool_name: str) -> bool:
    """Check if the tool mentioned in docs matches the version file."""
    tool_lower = tool.lower().replace(".", "")
    mapping = {
        "Ruby": ["ruby"],
        "Python": ["python"],
        "Node.js": ["node", "nodejs"],
        "Java": ["java"],
        "Terraform": ["terraform", "tf"],
    }
    return tool_lower in mapping.get(tool_name, [])


def _versions_match(doc_ver: str, file_ver: str) -> bool:
    """Return True when versions are equivalent (handles '20' vs '20.0')."""
    if doc_ver == file_ver:
        return True
    if file_ver.startswith(doc_ver + "."):
        return True
    if doc_ver.startswith(file_ver + "."):
        return True
    doc_parts = doc_ver.split(".")
    file_parts = file_ver.split(".")
    if len(doc_parts) >= 2 and len(file_parts) >= 2:
        return doc_parts[0] == file_parts[0] and doc_parts[1] == file_parts[1]
    return False
