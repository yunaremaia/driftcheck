"""NPMRC drift detection: .npmrc vs package.json settings.

Detects drift between npm configuration (.npmrc) and package.json fields
(engine-strict, publishConfig, etc.).
"""
from __future__ import annotations
import re

# Match engine-strict mentions in README
ENGINE_STRICT_RE = re.compile(r'engine.strict\s*[:=]\s*(true|false)', re.I)
PUBLISH_REGISTRY_RE = re.compile(r'(?:registry|publishRegistry)\s*[:=]\s*(?P<url>https?://[^\s"\']+)', re.I)


def parse_npmrc(text: str) -> dict[str, str]:
    """Parse .npmrc key=value pairs into a dict."""
    config = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip().strip('"').strip("'")
    return config


# Alias for backward compatibility
parse_npmrc_registry = parse_npmrc


def find_npmrc_drift(
    npmrc_content: str | None,
    package_json_content: str | None,
    docs: dict[str, str],
) -> list[dict]:
    """Detect drift between .npmrc and package.json settings."""
    drifts = []
    
    if not npmrc_content:
        return drifts
    
    npmrc = parse_npmrc(npmrc_content)
    
    # Check engine-strict consistency
    if "engine-strict" in npmrc:
        npmrc_val = npmrc["engine-strict"].lower() == "true"
        if package_json_content:
            pkg_engines = _extract_package_json_field(package_json_content, "engines")
            if pkg_engines and npmrc_val:
                # engine-strict=true with engines field is consistent
                pass
            elif not pkg_engines and npmrc_val:
                drifts.append({
                    "file": ".npmrc",
                    "detail": "engine-strict=true but package.json has no engines field",
                    "npmrc_setting": "engine-strict=true",
                })
    
    # Check publish registry consistency
    if "registry" in npmrc:
        registry = npmrc["registry"]
        if package_json_content:
            publish_config = _extract_package_json_nested_field(package_json_content, "publishConfig", "registry")
            if publish_config and publish_config != registry:
                drifts.append({
                    "file": ".npmrc",
                    "detail": f".npmrc registry={registry} but package.json publishConfig.registry={publish_config}",
                    "npmrc_registry": registry,
                    "package_json_registry": publish_config,
                })
    
    # Check tag-version-prefix consistency
    if "tag-version-prefix" in npmrc:
        prefix = npmrc["tag-version-prefix"]
        if prefix != "v":
            drifts.append({
                "file": ".npmrc",
                "detail": f"tag-version-prefix={prefix} (non-standard, expected 'v')",
                "npmrc_setting": f"tag-version-prefix={prefix}",
            })
    
    return drifts


def _extract_package_json_field(text: str, field: str) -> str | None:
    """Extract a top-level field from package.json."""
    pattern = rf'"{field}"\s*:\s*"([^"]+)"'
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _extract_package_json_nested_field(text: str, section: str, field: str) -> str | None:
    """Extract a nested field from package.json (e.g., publishConfig.registry)."""
    pattern = rf'"{section}"\s*:\s*\{{[^}}]*"{field}"\s*:\s*"([^"]+)"'
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1) if m else None
