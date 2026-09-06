"""Kubernetes drift detection: image tags in manifests vs README."""
from __future__ import annotations
import re

K8S_IMAGE_RE = re.compile(r'image:\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)')
K8S_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)


def parse_k8s_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of container images in K8s manifests."""
    result = {}
    for m in K8S_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result


def find_k8s_drift(k8s_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between K8s image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in k8s_files.items():
        for image, tag in parse_k8s_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, k8s_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == k8s_tag:
            return True
        if k8s_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(k8s_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in K8S_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for k8s_img, k8s_tag in all_images.items():
                if img and img not in k8s_img and k8s_img not in img:
                    continue
                if not tags_match(tag, k8s_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or k8s_img}:{tag}",
                        "k8s_image": f"{k8s_img}:{k8s_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
