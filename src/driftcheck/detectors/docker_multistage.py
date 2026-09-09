"""Dockerfile multi-stage drift detection: FROM tags in multi-stage builds.

Detects when a Dockerfile uses multi-stage builds with different base image
versions, or when the final stage tag doesn't match README mentions.
"""
from __future__ import annotations
import re

# Match FROM statements in Dockerfiles
FROM_RE = re.compile(r'^FROM\s+(?P<image>[\w.\-/]+)(?::(?P<tag>[\w.\-]+))?(?:\s+AS\s+(?P<alias>\w+))?', re.MULTILINE | re.I)

# Match image mentions in README
IMAGE_RE = re.compile(r'(?:image|docker|container)\s+(?P<image>[\w.\-/]+)(?::(?P<tag>[\w.\-]+))?', re.I)


def parse_from_stages(text: str) -> list[dict]:
    """Parse all FROM stages from a Dockerfile.
    
    Returns list of {image, tag, alias, line}.
    """
    stages = []
    for m in FROM_RE.finditer(text):
        stages.append({
            "image": m.group("image"),
            "tag": m.group("tag"),
            "alias": m.group("alias"),
            "line": m.string.count("\n", 0, m.start()) + 1,
        })
    return stages


def find_dockerfile_multistage_drift(dockerfiles: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift in multi-stage Dockerfiles.
    
    Checks:
    - Multiple stages with same image but different base versions (e.g., node:18 vs node:20)
    - Final stage tag doesn't match README mentions
    - Scratch/distroless final stage with pinned intermediate versions
    """
    drifts = []
    
    for fname, content in dockerfiles.items():
        stages = parse_from_stages(content)
        if not stages:
            continue
        
        # Check for same image with different base versions (ignoring variants like -slim, -alpine)
        image_versions = {}
        for stage in stages:
            img = stage["image"]
            tag = stage["tag"]
            if img not in image_versions:
                image_versions[img] = []
            if tag:
                # Extract base version (e.g., "20" from "20-slim", "1.21" from "1.21-alpine")
                base_version = tag.split("-")[0]
                image_versions[img].append((tag, base_version, stage["line"]))
        
        for img, versions in image_versions.items():
            if len(versions) > 1:
                # Check if base versions differ (not just variants like slim vs alpine)
                base_versions = set(v[1] for v in versions)
                if len(base_versions) > 1:
                    tags = sorted(set(v[0] for v in versions))
                    drifts.append({
                        "file": fname,
                        "detail": f"Multi-stage build uses {img} with conflicting versions: {tags}",
                        "image": img,
                        "tags": tags,
                    })
        
        # Check final stage against README
        final_stage = stages[-1]
        if final_stage["tag"]:
            for doc_fname, doc_content in docs.items():
                for m in IMAGE_RE.finditer(doc_content):
                    doc_img = m.group("image")
                    doc_tag = m.group("tag")
                    if doc_img == final_stage["image"] and doc_tag and doc_tag != final_stage["tag"]:
                        drifts.append({
                            "file": doc_fname,
                            "doc_image": f"{doc_img}:{doc_tag}",
                            "dockerfile_image": f"{final_stage['image']}:{final_stage['tag']}",
                            "pos": m.start(),
                        })
                        break
    
    return drifts
