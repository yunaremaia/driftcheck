"""Helm drift detection: Chart.yaml/values.yaml image tags vs README."""
from __future__ import annotations
import re

HELM_IMAGE_RE = re.compile(r'(?:repository|image):\s*["\']?(?P<image>[\w.\-/]+)["\']?\s*\n\s*(?:tag|version):\s*["\']?(?P<tag>[\w.\-]+)["\']?', re.I)
HELM_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)


def parse_helm_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of images in Helm Chart.yaml/values.yaml."""
    result = {}
    for m in HELM_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result


def find_helm_drift(helm_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Helm chart image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in helm_files.items():
        for image, tag in parse_helm_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, helm_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == helm_tag:
            return True
        if helm_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(helm_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in HELM_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for helm_img, helm_tag in all_images.items():
                if img and img not in helm_img and helm_img not in img:
                    continue
                if not tags_match(tag, helm_tag):
                    drifts.append({
                        "file": fname,
                        "doc_version": f"{img or helm_img}:{tag}",
                        "helm_image": f"{helm_img}:{helm_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
