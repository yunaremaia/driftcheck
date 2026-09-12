"""Dockerfile base image drift detection: detect unpinned and floating base images.

Flags Dockerfiles using `:latest`, `:stable`, or no tag at all — these create
non-reproducible builds and silently pull in breaking changes. Also detects
when sibling Dockerfiles (e.g., Dockerfile.dev vs Dockerfile.prod) pin
different versions of the same base image.
"""
from __future__ import annotations
import re

FROM_LINE_RE = re.compile(
    r'^FROM\s+(?:--platform=\S+\s+)?(?P<image>[\w.\-/]+)(?::(?P<tag>[\w.\-]+))?(?:\s+AS\s+(?P<alias>\w+))?',
    re.MULTILINE | re.I
)

FLOATING_TAGS = {'latest', 'stable', 'current', 'testing', 'nightly'}


def parse_dockerfile_bases(text: str) -> list[dict]:
    """Return list of {image, tag, alias, line, floating} from a Dockerfile."""
    stages = []
    for m in FROM_LINE_RE.finditer(text):
        tag = m.group('tag')
        stages.append({
            'image': m.group('image'),
            'tag': tag,
            'alias': m.group('alias'),
            'line': m.string.count('\n', 0, m.start()) + 1,
            'floating': tag is None or tag.lower() in FLOATING_TAGS,
        })
    return stages


def find_dockerfile_bases_drift(dockerfiles: dict[str, str], docs: dict[str, str] | None = None) -> list[dict]:
    """Detect floating/unpinned base images and sibling Dockerfile drift.

    Two detection modes:
    1. Floating tag: any FROM using :latest, :stable, :nightly, or no tag.
    2. Sibling divergence: Dockerfile.dev and Dockerfile.prod using different
       versions of the same base image.
    """
    drifts = []

    # Group Dockerfiles by base image for sibling comparison
    bases_by_image: dict[str, list[dict]] = {}

    for fname, content in dockerfiles.items():
        for stage in parse_dockerfile_bases(content):
            img = stage['image']

            # Mode 1 — floating tag
            if stage['floating']:
                drifts.append({
                    'file': fname,
                    'line': stage['line'],
                    'image': img,
                    'tag': stage['tag'] or '(none)',
                    'detail': f'{img}:{stage["tag"] or ""} uses {"implicit latest" if stage["tag"] is None else "floating tag " + stage["tag"]}',
                })

            # Collect for sibling comparison (include all, not just pinned)
            bases_by_image.setdefault(img, []).append({
                'file': fname,
                'tag': stage['tag'],
                'alias': stage['alias'],
                'line': stage['line'],
                'floating': stage['floating'],
            })

    # Mode 2 — sibling Dockerfile drift
    for img, entries in bases_by_image.items():
        if len(entries) < 2:
            continue
        tags = set(e['tag'] for e in entries)
        if len(tags) > 1:
            files = sorted(set(e['file'] for e in entries))
            drifts.append({
                'file': files[0],
                'image': img,
                'tags': sorted(tags),
                'detail': f'{img} pinned differently across {", ".join(files)}: {sorted(tags)}',
            })

    return drifts
