"""Gradle Version Catalog drift detection: libs.versions.toml vs README."""

import re
from pathlib import Path

LIBS_VERSIONS_RE = re.compile(
    r'\[versions?\]\s*(.+?)(?=\[|$)', re.DOTALL
)
LIBS_PLUGIN_RE = re.compile(
    r'plugin\.([a-zA-Z0-9_-]+)\s*=\s*["\']([0-9.]+)["\']'
)
LIBS_LIBRARY_VER_RE = re.compile(
    r'([a-zA-Z0-9_-]+)\s*=\s*\{[^}]*version\s*=\s*["\']([0-9.]+)["\']'
)


def parse_gradle_catalog(filepath):
    """Parse libs.versions.toml and return dict of module -> version."""
    versions = {}
    try:
        content = Path(filepath).read_text()
        # Find [versions] section
        ver_match = LIBS_VERSIONS_RE.search(content)
        if ver_match:
            for m in LIBS_LIBRARY_VER_RE.finditer(ver_match.group(1)):
                versions[m.group(1)] = m.group(2)
        # Find plugin versions in [plugins] section
        plugins_match = re.search(r'\[plugins?\]\s*(.+?)(?=\[|$)', content, re.DOTALL)
        if plugins_match:
            for m in LIBS_PLUGIN_RE.finditer(plugins_match.group(1)):
                versions[f"plugin:{m.group(1)}"] = m.group(2)
    except (FileNotFoundError, PermissionError):
        pass
    return versions


def find_gradle_catalog_drift(root_path):
    """Find drift in libs.versions.toml vs README."""
    root = Path(root_path)
    catalog_files = list(root.glob("gradle/libs.versions.toml")) + list(root.glob("libs.versions.toml"))
    
    if not catalog_files:
        return []
    
    catalog_versions = parse_gradle_catalog(catalog_files[0])
    
    # Read README for comparison
    readme_files = list(root.glob("README*.md")) + list(root.glob("docs/README*.md"))
    drifts = []
    
    for readme_path in readme_files:
        try:
            readme_text = readme_path.read_text()
            for lib, ver in catalog_versions.items():
                # Look for version mentions in README
                pattern = rf'{re.escape(lib)}\s*[:=]?\s*["\']?([0-9.]+)'
                for m in re.finditer(pattern, readme_text, re.I):
                    if m.group(1) != ver:
                        drifts.append({
                            "type": "gradle_catalog_drift",
                            "file": "libs.versions.toml",
                            "library": lib,
                            "catalog_version": ver,
                            "readme_version": m.group(1),
                            "message": f"{lib}: catalog={ver}, README={m.group(1)}",
                        })
        except (FileNotFoundError, PermissionError):
            pass
    
    return drifts
