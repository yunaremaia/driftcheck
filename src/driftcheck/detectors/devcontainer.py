"""Devcontainer drift detection: devcontainer.json vs README mentions."""
from __future__ import annotations
import re
import json

DEVCONTAINER_IMAGE_RE = re.compile(r'"image"\s*:\s*"(?P<image>[^"]+)"')
DEVCONTAINER_DOC_RE = re.compile(
    r'(?:dev\s*container|remote\s*container|vscode\s*container|containerized)\s+(?P<ver>\d[\d.]*)',
    re.I
)


def parse_devcontainer_image(text: str) -> str | None:
    """Parse image from devcontainer.json. Returns image string or None."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    image = data.get("image")
    if image:
        return image
    build = data.get("build", {})
    if isinstance(build, dict) and build.get("dockerfile"):
        return build["dockerfile"]
    return None


def parse_devcontainer_features(text: str) -> dict[str, str]:
    """Parse features from devcontainer.json. Returns {name: version}."""
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    features = data.get("features", {})
    result = {}
    for name, value in features.items():
        if isinstance(value, str):
            result[name] = value
        elif isinstance(value, dict):
            version = value.get("version")
            if version:
                result[name] = str(version)
    return result


def _extract_image_version(image: str) -> str | None:
    """Extract version tag from a docker image string.
    
    Handles:
    - mcr.microsoft.com/devcontainers/rust:1.70 -> 1.70
    - rust:1.70 -> 1.70
    - ubuntu:22.04 -> 22.04
    - nginx:latest -> latest (non-numeric, ignored)
    """
    if ":" not in image:
        return None
    tag = image.split(":")[-1]
    # Skip non-numeric tags like "latest", "bullseye"
    if re.match(r'^\d', tag):
        return tag
    return None


def find_devcontainer_drift(devcontainer_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect drift between devcontainer.json and README mentions.

    Detects:
    1. Image version drift (e.g., image: "rust:1.70" vs README says "rust 1.68")
    2. Feature version drift (feature version vs README mention)

    Returns list of {file, doc_version, devcontainer_version, feature, pos}.
    """
    if not devcontainer_text:
        return []
    drifts = []
    try:
        data = json.loads(devcontainer_text)
    except (json.JSONDecodeError, ValueError):
        return []

    image = data.get("image", "")
    features = data.get("features", {})

    # Check image version drift
    image_ver = _extract_image_version(image)
    if image_ver:
        # Extract base name for matching (e.g., "rust" from "rust:1.70")
        image_base = image.split(":")[0].split("/")[-1]
        for fname, content in docs.items():
            # Look for mentions like "rust 1.68", "rust:1.68", "uses rust 1.68"
            doc_re = re.compile(
                rf'(?:uses?|using|with|runs?|on|from)\s+{re.escape(image_base)}[\s:]+(?P<ver>\d[\d.]*)|{re.escape(image_base)}[\s:]+(?P<ver2>\d[\d.]*)',
                re.I
            )
            for m in doc_re.finditer(content):
                dv = m.group("ver") or m.group("ver2")
                if dv and dv != image_ver:
                    drifts.append({
                        "file": fname,
                        "doc_version": dv,
                        "devcontainer_version": image_ver,
                        "feature": f"image:{image_base}",
                        "pos": m.start(),
                    })
                    break

    # Check feature version drift (best-effort, matches short names)
    for feat_name, feat_version in features.items():
        if isinstance(feat_version, dict):
            feat_version = feat_version.get("version", "")
        if not feat_version:
            continue
        # Only match on the short part (e.g., "docker-in-docker" from ghcr.io/.../docker-in-docker:2)
        short_name = feat_name.split("/")[-1].split(":")[0]
        if "-" not in short_name or len(short_name) < 4:
            continue
        for fname, content in docs.items():
            doc_re = re.compile(
                rf'{re.escape(short_name)}[\s/]+v?(?P<ver>\d[\d.]*)',
                re.I
            )
            for m in doc_re.finditer(content):
                dv = m.group("ver")
                if dv != str(feat_version).lstrip("v"):
                    drifts.append({
                        "file": fname,
                        "doc_version": dv,
                        "devcontainer_version": str(feat_version),
                        "feature": short_name,
                        "pos": m.start(),
                    })
                    break

    return drifts
