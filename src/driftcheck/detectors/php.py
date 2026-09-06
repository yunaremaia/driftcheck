"""PHP/Composer drift detection: composer.json require.php vs README mentions."""
from __future__ import annotations
import re

COMPOSER_PHP_RE = re.compile(r'"php"\s*:\s*"(?P<ver>[^\"]+)"')
PHP_DOC_RE = re.compile(
    r'(?:requires?|minimum|supports?|version|with|needs?|running)\s+PHP\s+(?P<ver>\d+(?:\.\d+)?)|(?<!\w)PHP\s+(?P<ver2>\d+(?:\.\d+)?)(?=\s|$|,|\\.|;)',
    re.I
)


def parse_composer_php_version(text: str) -> str | None:
    """Parse PHP version from composer.json require.php. Returns major.minor (e.g., '8.2')."""
    m = COMPOSER_PHP_RE.search(text)
    if not m:
        return None
    ver = m.group("ver")
    # Handle ranges like "^8.2", ">=8.2", "~8.2", "8.2.*"
    ver = re.sub(r'[\^~>=<]+', '', ver).strip()
    ver = ver.replace('.*', '')
    parts = ver.split('.')
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return ver


def find_php_drift(composer_text: str, docs: dict[str, str]) -> list[dict]:
    """Detect PHP version drift between composer.json and README mentions.

    Returns list of {file, doc_version, composer_version, pos}.
    Only flags when the doc's PHP major.minor doesn't match composer.json.
    """
    if not composer_text:
        return []
    cv = parse_composer_php_version(composer_text)
    if not cv:
        return []
    cv_major_minor = ".".join(cv.split(".")[:2])
    drifts = []
    for fname, content in docs.items():
        for m in PHP_DOC_RE.finditer(content):
            dv = m.group("ver") or m.group("ver2")
            if dv is None:
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:m.end()].strip()
            if re.match(r'^\d+\.', line):
                continue
            dv_major_minor = ".".join(dv.split(".")[:2])
            if dv_major_minor != cv_major_minor:
                drifts.append({
                    "file": fname,
                    "doc_version": dv,
                    "composer_version": cv,
                    "pos": m.start(),
                })
                break
    return drifts
