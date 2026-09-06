"""Dependabot drift detection: ecosystems used vs dependabot.yml coverage."""
from __future__ import annotations
import re
from pathlib import Path

DEPENDABOT_RE = re.compile(r'package-ecosystem:\s*"(?P<ecosystem>[^"]+)"', re.I)

# Map of ecosystem -> files that indicate usage
ECOSYSTEM_FILES = {
    "npm": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
    "pip": ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg"],
    "gomod": ["go.mod"],
    "cargo": ["Cargo.toml"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "docker": ["Dockerfile", "docker-compose.yml", "compose.yaml"],
    "github-actions": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "bundler": ["Gemfile"],
    "composer": ["composer.json"],
    "mix": ["mix.exs"],
    "nuget": ["*.csproj", "*.sln"],
    "pub": ["pubspec.yaml"],
}


def find_dependabot_drift(root: Path) -> list[dict]:
    """Detect ecosystems used by the repo but not covered by dependabot.yml."""
    # Find which ecosystems are in use
    used_ecosystems = set()
    for eco, patterns in ECOSYSTEM_FILES.items():
        for pattern in patterns:
            if list(root.glob(pattern)):
                used_ecosystems.add(eco)
                break

    if not used_ecosystems:
        return []

    # Check dependabot.yml
    dependabot_path = root / ".github" / "dependabot.yml"
    if not dependabot_path.exists():
        dependabot_path = root / ".github" / "dependabot.yaml"

    if not dependabot_path.exists():
        # No dependabot at all — report all used ecosystems as missing
        return [{
            "file": ".github/dependabot.yml",
            "kind": "dependabot_missing",
            "ecosystems": sorted(used_ecosystems),
            "detail": f"dependabot.yml not found but ecosystems in use: {', '.join(sorted(used_ecosystems))}",
        }]

    # Parse existing dependabot config
    try:
        text = dependabot_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    configured = set()
    for m in DEPENDABOT_RE.finditer(text):
        configured.add(m.group("ecosystem").lower())

    missing = used_ecosystems - configured
    if not missing:
        return []

    return [{
        "file": ".github/dependabot.yml",
        "kind": "dependabot_incomplete",
        "ecosystems": sorted(missing),
        "configured": sorted(configured),
        "detail": f"dependabot.yml missing ecosystems: {', '.join(sorted(missing))} (configured: {', '.join(sorted(configured))})",
    }]
