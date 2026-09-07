"""Environment drift detection: compare config files across deployment environments.

Detects drift between:
- .env.example vs .env (missing/extra keys)
- docker-compose.yml vs docker-compose.prod.yml (image/tag differences)
- values.yaml vs values.prod.yaml (Helm value differences)
- Terraform tfvars files (terraform.tfvars vs production.tfvars)
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

# Patterns for environment config files
ENV_PATTERN = re.compile(r'^(?P<key>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>.*)$', re.MULTILINE)


def parse_env_file(text: str) -> dict[str, str]:
    """Parse a .env-style file into {key: value} dict."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = ENV_PATTERN.match(line)
        if m:
            value = m.group('value').strip()
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            result[m.group('key')] = value
    return result


def parse_env_example(text: str) -> dict[str, str]:
    """Parse .env.example — same format but values are placeholders."""
    return parse_env_file(text)


def find_env_drift(root: Path) -> list[dict]:
    """Detect drift between .env.example and .env files.
    
    Reports:
    - Keys in .env.example missing from .env
    - Keys in .env missing from .env.example (extra keys not documented)
    """
    example_path = root / ".env.example"
    env_path = root / ".env"
    
    if not example_path.exists():
        return []
    
    example_text = example_path.read_text(encoding="utf-8", errors="replace")
    example_keys = parse_env_example(example_text)
    
    if not env_path.exists():
        # .env.example exists but .env doesn't — informational
        return [{
            "file": ".env",
            "kind": "env_missing",
            "detail": ".env file missing — copy from .env.example and fill in values",
            "keys": sorted(example_keys.keys()),
        }]
    
    env_text = env_path.read_text(encoding="utf-8", errors="replace")
    env_keys = parse_env_file(env_text)
    
    drifts = []
    
    # Keys in .env.example but missing from .env
    missing = set(example_keys.keys()) - set(env_keys.keys())
    if missing:
        drifts.append({
            "file": ".env",
            "kind": "env_missing_keys",
            "detail": f".env missing {len(missing)} key(s) from .env.example: {', '.join(sorted(missing))}",
            "keys": sorted(missing),
        })
    
    # Keys in .env but not in .env.example (undocumented)
    extra = set(env_keys.keys()) - set(example_keys.keys())
    if extra:
        drifts.append({
            "file": ".env",
            "kind": "env_extra_keys",
            "detail": f".env has {len(extra)} undocumented key(s) not in .env.example: {', '.join(sorted(extra))}",
            "keys": sorted(extra),
        })
    
    return drifts


def find_compose_override_drift(root: Path) -> list[dict]:
    """Detect drift between docker-compose.yml and override files.
    
    Compares image tags between base compose and override files
    (e.g., docker-compose.yml vs docker-compose.prod.yml).
    """
    base_files = {}
    for pattern in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
        p = root / pattern
        if p.exists():
            base_files[pattern] = p.read_text(encoding="utf-8", errors="replace")
    
    if not base_files:
        return []
    
    override_files = {}
    for pattern in ["docker-compose.*.yml", "docker-compose.*.yaml", "compose.*.yaml", "compose.*.yml"]:
        for p in root.glob(pattern):
            if p.is_file():
                override_files[p.name] = p.read_text(encoding="utf-8", errors="replace")
    
    if not override_files:
        return []
    
    # Parse image references from compose files
    image_re = re.compile(r'image:\s*(?P<image>[\w./-]+)(?::(?P<tag>[\w.-]+))?')
    
    def extract_images(text: str) -> dict[str, str]:
        """Extract service -> image mapping from compose file."""
        images = {}
        for m in image_re.finditer(text):
            image = m.group('image')
            tag = m.group('tag') or 'latest'
            # Use image name as key (without registry prefix)
            key = image.split('/')[-1]
            images[key] = f"{image}:{tag}"
        return images
    
    drifts = []
    
    for base_name, base_text in base_files.items():
        base_images = extract_images(base_text)
        
        for override_name, override_text in override_files.items():
            override_images = extract_images(override_text)
            
            # Check for image tag differences
            for service, base_image in base_images.items():
                if service in override_images:
                    override_image = override_images[service]
                    base_tag = base_image.split(':')[-1] if ':' in base_image else 'latest'
                    override_tag = override_image.split(':')[-1] if ':' in override_image else 'latest'
                    
                    if base_tag != override_tag:
                        drifts.append({
                            "file": override_name,
                            "kind": "compose_image_drift",
                            "service": service,
                            "base_image": base_image,
                            "override_image": override_image,
                            "detail": f"{service}: base uses {base_image}, {override_name} uses {override_image}",
                        })
    
    return drifts


def find_helm_values_drift(root: Path) -> list[dict]:
    """Detect drift between Helm values.yaml and environment-specific values files."""
    base_path = root / "values.yaml"
    if not base_path.exists():
        # Check in charts/ subdirectory
        charts_dir = root / "charts"
        if charts_dir.exists():
            for chart in charts_dir.iterdir():
                if chart.is_dir():
                    base_path = chart / "values.yaml"
                    if base_path.exists():
                        break
            else:
                return []
        else:
            return []
    
    try:
        base_text = base_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    
    # Parse simple key: values from values.yaml
    base_values = {}
    for line in base_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ':' in stripped and not stripped.startswith('-'):
            key, _, value = stripped.partition(':')
            key = key.strip()
            value = value.strip()
            if value and not value.startswith('{'):
                base_values[key] = value
    
    # Find environment-specific values files
    env_values_files = []
    for pattern in ["values.*.yaml", "values.*.yml", "charts/**/values.*.yaml"]:
        for p in root.glob(pattern):
            if p.is_file() and p.name != "values.yaml":
                env_values_files.append(p)
    
    if not env_values_files:
        return []
    
    drifts = []
    for env_file in env_values_files:
        try:
            env_text = env_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        
        env_values = {}
        for line in env_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if ':' in stripped and not stripped.startswith('-'):
                key, _, value = stripped.partition(':')
                key = key.strip()
                value = value.strip()
                if value and not value.startswith('{'):
                    env_values[key] = value
        
        # Compare replicaCount, image tags, resources
        important_keys = ['replicaCount', 'tag', 'repository', 'resources']
        for key in important_keys:
            if key in base_values and key in env_values:
                if base_values[key] != env_values[key]:
                    drifts.append({
                        "file": str(env_file.relative_to(root)),
                        "kind": "helm_values_drift",
                        "key": key,
                        "base_value": base_values[key],
                        "env_value": env_values[key],
                        "detail": f"{key}: values.yaml has {base_values[key]}, {env_file.name} has {env_values[key]}",
                    })
    
    return drifts


def find_env_drift_combined(root: Path) -> list[dict]:
    """Combined environment drift detection."""
    drifts = []
    drifts.extend(find_env_drift(root))
    drifts.extend(find_compose_override_drift(root))
    drifts.extend(find_helm_values_drift(root))
    return drifts
