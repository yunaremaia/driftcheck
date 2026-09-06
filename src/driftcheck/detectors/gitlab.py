"""GitLab CI drift detection: .gitlab-ci.yml image tags vs README."""
from __future__ import annotations
import re

GITLAB_IMAGE_RE = re.compile(r'image:\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)')
GITLAB_VER_RE = re.compile(r'(?:image|docker|version)\s+(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)


def parse_gitlab_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of docker images in GitLab CI config."""
    result = {}
    for m in GITLAB_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result


def find_gitlab_drift(gitlab_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between GitLab CI docker image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in gitlab_files.items():
        for image, tag in parse_gitlab_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, ci_tag: str) -> bool:
        """Return True when tags are equivalent (handles '24' vs '24-slim')."""
        if doc_tag == ci_tag:
            return True
        if ci_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(ci_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in GITLAB_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for ci_img, ci_tag in all_images.items():
                if img and img not in ci_img and ci_img not in img:
                    continue
                if not tags_match(tag, ci_tag):
                    drifts.append({
                        "file": fname,
                        "doc_image": f"{img or ci_img}:{tag}",
                        "gitlab_image": f"{ci_img}:{ci_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
