"""Docker drift detection: Dockerfile FROM tags vs README mentions."""
from __future__ import annotations
import re

DOCKER_FROM_RE = re.compile(r'^FROM\s+(?:--\S+\s+)?(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)', re.MULTILINE | re.I)
DOCKER_TAG_RE = re.compile(r'(?:Docker|image)\s+(?P<image>[\w.\-]+):(?P<tag>[\w.\-]+)|(?:Docker|image)\s+(?:version|tag)?\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)


def parse_dockerfile_from(text: str) -> dict[str, str]:
    """Return {image: tag} map of FROM instructions in a Dockerfile."""
    result = {}
    for m in DOCKER_FROM_RE.finditer(text):
        result[m.group("image").lower()] = m.group("tag")
    return result


def find_docker_drift(dockerfiles: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Dockerfile FROM tags and README mentions.

    Scans docs for patterns like 'node:24' or 'Docker node 22' and compares
    to the actual FROM tag in the Dockerfile. Returns drifts where the doc
    mentions a different version than what the Dockerfile pins.
    """
    # Collect all FROM tags across dockerfiles
    all_from: dict[str, str] = {}
    for fname, content in dockerfiles.items():
        for image, tag in parse_dockerfile_from(content).items():
            all_from[image] = tag

    if not all_from:
        return []

    def tags_match(doc_tag: str, from_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == from_tag:
            return True
        # '24' matches '24-slim', '24-alpine', etc.
        if from_tag.startswith(doc_tag + "-"):
            return True
        # '24-slim' matches '24'
        if doc_tag.startswith(from_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in DOCKER_TAG_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            # Match by image name (node, python, golang, etc.)
            for from_img, from_tag in all_from.items():
                if img and img not in from_img and from_img not in img:
                    continue
                if not tags_match(tag, from_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or from_img}:{tag}",
                        "dockerfile_image": f"{from_img}:{from_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
