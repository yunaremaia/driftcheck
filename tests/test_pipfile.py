"""Tests for Pipfile drift detection: Pipfile vs Pipfile.lock version mismatches."""
from __future__ import annotations
import tempfile
from pathlib import Path

import pytest

from driftcheck.detectors.pipfile import (
    parse_pipfile_versions,
    parse_pipfile_lock_versions,
    find_pipfile_drift,
    PIPFILE_RE,
    PIPFILE_LOCK_RE,
)


class TestParsePipfileVersions:
    def test_single_package(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text('[packages]\nrequests = "==2.28.0"')
        result = parse_pipfile_versions(str(p))
        assert result == {"requests": "==2.28.0"}

    def test_multiple_packages(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text('[packages]\nrequests = "==2.28.0"\nflask = "==2.0.0"')
        result = parse_pipfile_versions(str(p))
        assert result == {"requests": "==2.28.0", "flask": "==2.0.0"}

    def test_empty(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text("")
        assert parse_pipfile_versions(str(p)) == {}

    def test_skip_source(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text('[source]\nurl = "https://pypi.org"')
        result = parse_pipfile_versions(str(p))
        assert result == {}

    def test_skip_requires(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text('[requires]\npython_version = "3.10"')
        result = parse_pipfile_versions(str(p))
        assert result == {}

    def test_wildcard(self, tmp_path):
        p = tmp_path / "Pipfile"
        p.write_text('[packages]\nrequests = "*"')
        result = parse_pipfile_versions(str(p))
        assert result == {"requests": "*"}


class TestParsePipfileLockVersions:
    def test_single_package(self, tmp_path):
        p = tmp_path / "Pipfile.lock"
        p.write_text('{\n    "default": {\n        "requests": {\n            "version": "==2.28.0"\n        }\n    }\n}')
        result = parse_pipfile_lock_versions(str(p))
        assert result == {"requests": "==2.28.0"}

    def test_multiple_packages(self, tmp_path):
        p = tmp_path / "Pipfile.lock"
        p.write_text('{\n    "default": {\n        "requests": {\n            "version": "==2.28.0"\n        },\n        "flask": {\n            "version": "==2.0.0"\n        }\n    }\n}')
        result = parse_pipfile_lock_versions(str(p))
        assert result == {"requests": "==2.28.0", "flask": "==2.0.0"}

    def test_empty(self, tmp_path):
        p = tmp_path / "Pipfile.lock"
        p.write_text("")
        assert parse_pipfile_lock_versions(str(p)) == {}


class TestFindPipfileDrift:
    def test_drift_detected(self, tmp_path):
        (tmp_path / "Pipfile").write_text('[packages]\nrequests = "==2.28.0"')
        (tmp_path / "Pipfile.lock").write_text(
            '{\n    "default": {\n        "requests": {\n            "version": "==2.25.0"\n        }\n    }\n}'
        )
        result = find_pipfile_drift(str(tmp_path))
        assert len(result) == 1
        assert result[0]["type"] == "pipfile_drift"
        assert result[0]["package"] == "requests"

    def test_no_drift(self, tmp_path):
        (tmp_path / "Pipfile").write_text('[packages]\nrequests = "==2.28.0"')
        (tmp_path / "Pipfile.lock").write_text(
            '{\n    "default": {\n        "requests": {\n            "version": "==2.28.0"\n        }\n    }\n}'
        )
        result = find_pipfile_drift(str(tmp_path))
        assert result == []

    def test_no_pipfile(self, tmp_path):
        (tmp_path / "Pipfile.lock").write_text('{}')
        result = find_pipfile_drift(str(tmp_path))
        assert result == []

    def test_no_pipfile_lock(self, tmp_path):
        (tmp_path / "Pipfile").write_text('[packages]\nrequests = "==2.28.0"')
        result = find_pipfile_drift(str(tmp_path))
        assert result == []

    def test_wildcard_no_drift(self, tmp_path):
        (tmp_path / "Pipfile").write_text('[packages]\nrequests = "*"')
        (tmp_path / "Pipfile.lock").write_text(
            '{\n    "default": {\n        "requests": {\n            "version": "==2.28.0"\n        }\n    }\n}'
        )
        result = find_pipfile_drift(str(tmp_path))
        assert result == []

    def test_multiple_packages(self, tmp_path):
        (tmp_path / "Pipfile").write_text(
            '[packages]\nrequests = "==2.28.0"\nflask = "==2.0.0"'
        )
        (tmp_path / "Pipfile.lock").write_text(
            '{\n    "default": {\n        "requests": {\n            "version": "==2.25.0"\n        },\n        "flask": {\n            "version": "==2.0.0"\n        }\n    }\n}'
        )
        result = find_pipfile_drift(str(tmp_path))
        assert len(result) == 1
        assert result[0]["package"] == "requests"


class TestPipfileRe:
    def test_match_package(self):
        m = PIPFILE_RE.search('requests = "==2.28.0"')
        assert m is not None
        assert m.group(1) == "requests"
        assert m.group(2) == "==2.28.0"

    def test_match_star(self):
        m = PIPFILE_RE.search('requests = "*"')
        assert m is not None

    def test_no_match(self):
        m = PIPFILE_RE.search('[packages]')
        assert m is None


class TestPipfileLockRe:
    def test_match_package(self):
        m = PIPFILE_LOCK_RE.search('"requests": {\n            "version": "==2.28.0"')
        assert m is not None
        assert m.group(1) == "requests"
        assert m.group(2) == "==2.28.0"

    def test_no_match(self):
        m = PIPFILE_LOCK_RE.search('"requests": {}')
        assert m is None
