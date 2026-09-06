"""Docker Compose drift detection: docker-compose.yml image tags vs README."""
from __future__ import annotations
import re

DC_IMAGE_RE = re.compile(r'^\s{4,}(?:image:\s*)(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)', re.MULTILINE)
DC_VER_RE = re.compile(r'(?:image|docker|container)?\s*(?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)|(?:version|tag)\s+(?P<tag2>[\d.]+[\w.\-]*)', re.I)


def parse_docker_compose_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of images in docker-compose.yml / compose.yaml."""
    result = {}
    for m in DC_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result


def find_docker_compose_drift(dc_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between docker-compose.yml image tags and README mentions."""
    all_images: dict[str, str] = {}
    for fname, content in dc_files.items():
        for image, tag in parse_docker_compose_images(content).items():
            all_images[image] = tag

    if not all_images:
        return []

    def tags_match(doc_tag: str, dc_tag: str) -> bool:
        if doc_tag == dc_tag:
            return True
        if dc_tag.startswith(doc_tag + "-"):
            return True
        if doc_tag.startswith(dc_tag + "-"):
            return True
        return False

    drifts = []
    for fname, content in docs.items():
        for m in DC_VER_RE.finditer(content):
            img = (m.group("image") or "").lower()
            tag = m.group("tag") or m.group("tag2")
            if not tag:
                continue
            for dc_img, dc_tag in all_images.items():
                if img and img not in dc_img and dc_img not in img:
                    continue
                if not tags_match(tag, dc_tag):
                    drifts.append({
                        "file": fname,
                        "doc_version": f"{img or dc_img}:{tag}",
                        "compose_image": f"{dc_img}:{dc_tag}",
                        "pos": m.start(),
                    })
                    break
            break  # one per file
    return drifts
