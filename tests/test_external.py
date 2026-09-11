"""Tests for external resource drift detection (external.py)."""
import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.external import (
    EXTERNAL_CDN_RE,
    find_external_resource_drift,
)


class TestExternalResourceRegex:
    """Test the CDN regex pattern."""

    def test_googleapis_fonts(self):
        url = "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap"
        m = EXTERNAL_CDN_RE.search(url)
        assert m is not None
        assert m.group("host") == "fonts.googleapis.com"

    def test_gstatic(self):
        url = "https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2"
        m = EXTERNAL_CDN_RE.search(url)
        assert m is not None
        assert m.group("host") == "fonts.gstatic.com"

    def test_jsdelivr(self):
        url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
        m = EXTERNAL_CDN_RE.search(url)
        assert m is not None
        assert m.group("host") == "cdn.jsdelivr.net"

    def test_unpkg(self):
        url = "https://unpkg.com/react@18.2.0/umd/react.production.min.js"
        m = EXTERNAL_CDN_RE.search(url)
        assert m is not None
        assert m.group("host") == "unpkg.com"

    def test_cdnjs(self):
        url = "https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.21/lodash.min.js"
        m = EXTERNAL_CDN_RE.search(url)
        assert m is not None
        assert m.group("host") == "cdnjs.cloudflare.com"

    def test_no_match_local(self):
        assert EXTERNAL_CDN_RE.search("/assets/fonts/inter.woff2") is None

    def test_no_match_other_domain(self):
        assert EXTERNAL_CDN_RE.search("https://example.com/foo.js") is None


class TestFindExternalResourceDrift:
    """Test the find_external_resource_drift function."""

    def _make_root(self, tmp_path: Path, html_content: str, rel_path: str = "archify/assets/template.html") -> Path:
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_content)
        return tmp_path

    def test_detects_googlefonts_in_template(self, tmp_path):
        html = """<!DOCTYPE html>
<html>
<head>
  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">
</head>
<body>Hello</body>
</html>"""
        root = self._make_root(tmp_path, html)
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["host"] == "fonts.googleapis.com"
        assert drifts[0]["kind"] == "external_resource"

    def test_no_drift_when_no_external(self, tmp_path):
        html = """<!DOCTYPE html>
<html>
<head>
  <link href="/assets/style.css" rel="stylesheet">
</head>
<body>Hello</body>
</html>"""
        root = self._make_root(tmp_path, html)
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 0

    def test_detects_in_examples(self, tmp_path):
        html = '<script src="https://cdn.jsdelivr.net/npm/vue@3"></script>'
        root = self._make_root(tmp_path, html, rel_path="examples/demo.html")
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["host"] == "cdn.jsdelivr.net"

    def test_detects_in_archify_examples(self, tmp_path):
        html = '<script src="https://unpkg.com/alpinejs@3"></script>'
        root = self._make_root(tmp_path, html, rel_path="archify/examples/demo.html")
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["host"] == "unpkg.com"

    def test_detects_in_docs_gallery(self, tmp_path):
        html = '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">'
        root = self._make_root(tmp_path, html, rel_path="docs/gallery/artifacts/sample.html")
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
        assert drifts[0]["host"] == "cdnjs.cloudflare.com"

    def test_one_drift_per_file(self, tmp_path):
        html = """<!DOCTYPE html>
<html>
<head>
  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/vue@3"></script>
</head>
<body></body>
</html>"""
        root = self._make_root(tmp_path, html)
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1  # one per file

    def test_empty_html(self, tmp_path):
        root = self._make_root(tmp_path, "")
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 0

    def test_no_candidates_dir(self, tmp_path):
        drifts = find_external_resource_drift(tmp_path)
        assert len(drifts) == 0

    def test_alt_template_path(self, tmp_path):
        html = '<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap">'
        root = self._make_root(tmp_path, html, rel_path="assets/template.html")
        drifts = find_external_resource_drift(root)
        assert len(drifts) == 1
