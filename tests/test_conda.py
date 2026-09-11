"""Tests for Conda drift detector."""
from pathlib import Path
import tempfile

import pytest

from driftcheck.detectors.conda import (
    parse_conda_environment,
    find_conda_drift,
)


class TestParseCondaEnvironment:
    def test_pinned_packages(self):
        text = "dependencies:\n  - python=3.10\n  - numpy>=1.24\n  - pandas==2.0"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_conda_environment(f.name)
        assert "numpy" in result
        assert "pandas" in result

    def test_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("")
            f.flush()
            result = parse_conda_environment(f.name)
        assert result == {}


class TestFindCondaDrift:
    def test_unpinned_detected(self, tmp_path):
        (tmp_path / "environment.yml").write_text("dependencies:\n  - numpy\n  - pandas\n")
        result = find_conda_drift(str(tmp_path))
        assert len(result) >= 1
        assert result[0]["type"] == "conda_drift"

    def test_no_environment_yml(self, tmp_path):
        result = find_conda_drift(str(tmp_path))
        assert result == []
