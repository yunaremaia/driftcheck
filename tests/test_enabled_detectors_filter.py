"""Regression tests for scan_repo(enabled_detectors=...).

driftcheck/detector.py filtered out non-selected detectors with
``set(DRIFT_KEYS) - enabled_detectors`` but never imported DRIFT_KEYS, so every
call that passed ``enabled_detectors`` raised NameError. The CLI reaches this
line through --only/--exclude, so detector selection was unusable.

Also pins the ``__all__`` surfaces these modules re-export: a name listed in
``__all__`` but absent from the module is an AttributeError on star-import.
ruff's F822 catches that on a plain ``__all__`` list but not on the entries
appended through the trailing ``__all__ +=`` in driftcheck.detectors.
"""
from __future__ import annotations

import pytest

import driftcheck
import driftcheck.detector as detector_mod
import driftcheck.detectors as detectors_mod
from driftcheck.config import DRIFT_KEYS
from driftcheck.detector import scan_repo


def _drift_keys(result: dict) -> set[str]:
    """The *_drifts keys scan_repo reports findings under."""
    return {key for key, value in result.items() if key.endswith("_drifts") and value}


class TestEnabledDetectorsFilter:
    """The enabled_detectors path must run, not raise."""

    def test_single_detector_does_not_raise_nameerror(self, tmp_path):
        """Regression: DRIFT_KEYS was used without being imported."""
        (tmp_path / "README.md").write_text("Requires Python 3.11\n", encoding="utf-8")

        result = scan_repo(
            tmp_path,
            enabled_detectors={"python_version_drifts"},
        )

        assert "toolchain_version" in result

    def test_selected_detector_still_reports_findings(self, tmp_path):
        """The filter must drop other detectors, not the selected one."""
        (tmp_path / "README.md").write_text("Requires Python 3.11\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1"\nrequires-python = ">=3.12"\n',
            encoding="utf-8",
        )

        result = scan_repo(tmp_path, enabled_detectors={"python_version_drifts"})

        findings = result["python_version_drifts"]
        assert findings, "the selected detector produced no finding"
        assert findings[0]["doc_version"] == "3.11"

    def test_empty_selection_excludes_every_named_detector(self, tmp_path):
        """Selecting nothing must leave no DRIFT_KEYS detector with findings."""
        (tmp_path / "README.md").write_text("Requires Python 3.11\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1"\nrequires-python = ">=3.12"\n',
            encoding="utf-8",
        )

        result = scan_repo(tmp_path, enabled_detectors=set())

        assert not (_drift_keys(result) & set(DRIFT_KEYS)), (
            f"detectors outside the empty selection reported findings: "
            f"{sorted(_drift_keys(result) & set(DRIFT_KEYS))}"
        )

    def test_unselected_detector_is_filtered_out(self, tmp_path):
        """A detector that does report is dropped when it is not selected."""
        (tmp_path / "README.md").write_text("Requires Python 3.11\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1"\nrequires-python = ">=3.12"\n',
            encoding="utf-8",
        )

        unfiltered = _drift_keys(scan_repo(tmp_path))
        assert "python_version_drifts" in unfiltered, (
            "fixture no longer produces a finding"
        )

        with_other = _drift_keys(
            scan_repo(tmp_path, enabled_detectors={"package_version_drifts"})
        )
        assert "python_version_drifts" not in with_other


@pytest.mark.parametrize(
    "module",
    [detector_mod, detectors_mod, driftcheck],
    ids=["driftcheck.detector", "driftcheck.detectors", "driftcheck"],
)
class TestAllMatchesNamespace:
    """__all__ must describe the module that declares it."""

    def test_every_exported_name_exists(self, module):
        missing = [name for name in module.__all__ if not hasattr(module, name)]
        assert missing == [], f"__all__ advertises names that do not exist: {missing}"

    def test_no_duplicated_entries(self, module):
        duplicated = sorted({n for n in module.__all__ if module.__all__.count(n) > 1})
        assert duplicated == [], f"duplicated entries in __all__: {duplicated}"

    def test_star_import_succeeds(self, module):
        """A stale __all__ entry makes `from <module> import *` raise."""
        namespace: dict[str, object] = {}
        exec(f"from {module.__name__} import *", namespace)
        assert len(namespace) - 1 == len(module.__all__)
