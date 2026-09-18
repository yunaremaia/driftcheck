"""Kotlin Multiplatform (KMP) drift detection: gradle/libs.versions.toml vs README badges."""

import re
from pathlib import Path

# KMP-specific version keys in libs.versions.toml
KMP_VERSION_KEYS = [
    "kotlin",
    "kotlin-coroutines",
    "compose-bom",
    "compose-compiler",
    "kgp",
    "agp",
    "ksp",
]

# Regex for extracting versions from README badge URLs
BADGE_RES: dict[str, re.Pattern] = {
    "kotlin": re.compile(
        r'(?:badge|shield)[/\w.-]*[Kk]otlin[/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "kotlin-coroutines": re.compile(
        r'(?:badge|shield)[/\w.-]*[Cc]oroutines[/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "compose-bom": re.compile(
        r'(?:badge|shield)[/\w.-]*[Cc][Oo][Mm][Pp][Oo][Ss][Ee][/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "compose-compiler": re.compile(
        r'(?:badge|shield)[/\w.-]*[Cc]ompiler[/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "kgp": re.compile(
        r'(?:badge|shield)[/\w.-]*[Kk][Gg][Pp][/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "agp": re.compile(
        r'(?:badge|shield)[/\w.-]*[Aa][Gg][Pp][/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
    "ksp": re.compile(
        r'(?:badge|shield)[/\w.-]*[Kk][Ss][Pp][/-]+v?(\d+\.\d+(?:\.\d+)?)',
    ),
}

# TOML [versions] section pattern
TOML_VERSIONS_RE = re.compile(r'\[versions?\]\s*(.+?)(?=\[|$)', re.DOTALL)

# TOML plugin section
TOML_PLUGINS_RE = re.compile(r'\[plugins?\]\s*(.+?)(?=\[|$)', re.DOTALL)

# TOML plugin with id and version
TOML_PLUGIN_WITH_VER_RE = re.compile(
    r'([a-zA-Z0-9_.-]+)\s*=\s*\{[^}]*version\s*=\s*["\']([^"\']+)["\']'
)

# TOML simple key = "value"
TOML_SIMPLE_KEY_RE = re.compile(
    r'^([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


def parse_kmp_versions(filepath: str) -> dict[str, str]:
    """Parse KMP-relevant versions from a libs.versions.toml file.

    Returns a dict mapping normalized key names to version strings.
    E.g., {"kotlin": "2.0.0", "compose-bom": "2024.01.00", "kgp": "2.0.0"}
    """
    versions: dict[str, str] = {}
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return versions

    # Parse [versions] section
    ver_match = TOML_VERSIONS_RE.search(content)
    if ver_match:
        section = ver_match.group(1)
        for line in section.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = TOML_SIMPLE_KEY_RE.match(line)
            if m:
                key, ver = m.group(1).strip(), m.group(2).strip()
                versions[key] = ver

    # Parse [plugins] section for plugin versions
    plug_match = TOML_PLUGINS_RE.search(content)
    if plug_match:
        section = plug_match.group(1)
        for line in section.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = TOML_PLUGIN_WITH_VER_RE.search(line)
            if m:
                key, ver = m.group(1).strip(), m.group(2).strip()
                versions[key] = ver

    return versions


def find_kotlin_multiplatform_drift(
    root_path: str | Path,
) -> list[dict]:
    """Detect drift between KMP versions in gradle/libs.versions.toml and README badges.

    Checks for version mismatches between TOML-declared versions and README
    badge URLs or prose mentions for Kotlin, Compose, Coroutines, KGP, AGP, KSP.

    Args:
        root_path: Path to the repository root.

    Returns:
        List of drift dicts with keys: type, file, library, catalog_version,
        readme_version, message.
    """
    root = Path(root_path)

    # Find libs.versions.toml
    catalog_files = (
        list(root.glob("gradle/libs.versions.toml"))
        + list(root.glob("libs.versions.toml"))
    )
    if not catalog_files:
        return []

    catalog_versions = parse_kmp_versions(str(catalog_files[0]))
    if not catalog_versions:
        return []

    # Filter to KMP-relevant keys only
    kmp_versions = {
        k: v for k, v in catalog_versions.items() if k in KMP_VERSION_KEYS
    }
    if not kmp_versions:
        return []

    # Read README files
    readme_files = list(root.glob("README*.md")) + list(root.glob("docs/README*.md"))
    if not readme_files:
        return []

    drifts: list[dict] = []

    for readme_path in readme_files:
        try:
            readme_text = readme_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for key, catalog_ver in kmp_versions.items():
            badge_pattern = BADGE_RES.get(key)
            if not badge_pattern:
                continue

            for m in badge_pattern.finditer(readme_text):
                readme_ver = m.group(1)
                # Compare: allow minor/patch tolerance for compose-bom
                if key == "compose-bom":
                    # Compose BOM uses date-like versions (2024.01.00), compare exactly
                    if readme_ver == catalog_ver:
                        continue
                else:
                    # For kotlin, coroutines, etc., compare major.minor
                    readme_parts = readme_ver.split(".")
                    catalog_parts = catalog_ver.split(".")
                    if (
                        len(readme_parts) >= 2
                        and len(catalog_parts) >= 2
                        and readme_parts[:2] == catalog_parts[:2]
                    ):
                        continue

                drifts.append({
                    "type": "kotlin_multiplatform_drift",
                    "file": str(readme_path.relative_to(root)),
                    "library": key,
                    "catalog_version": catalog_ver,
                    "readme_version": readme_ver,
                    "message": (
                        f"{key}: catalog={catalog_ver}, README badge={readme_ver}"
                    ),
                })

    return drifts
