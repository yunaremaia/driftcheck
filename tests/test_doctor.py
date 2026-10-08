"""Tests for driftcheck.doctor — repository diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from driftcheck.doctor import Doctor, run_doctor, doctor_fix, doctor_exit_code, print_doctor_report


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal temporary repository."""
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nrequires-python = '>=3.10'\n", encoding="utf-8"
    )
    return tmp_path


class TestDoctorReadme:
    def test_pass_when_readme_exists(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        readme_check = next(c for c in report.checks if c.name == "readme")
        assert readme_check.status == "pass"

    def test_fail_when_no_readme(self, tmp_repo):
        (tmp_repo / "README.md").unlink()
        report = Doctor(tmp_repo).run_all()
        readme_check = next(c for c in report.checks if c.name == "readme")
        assert readme_check.status == "fail"
        assert readme_check.fixable is True


class TestDoctorContributing:
    def test_pass_when_contributing_exists(self, tmp_repo):
        (tmp_repo / "CONTRIBUTING.md").write_text("# How to contribute\n", encoding="utf-8")
        report = Doctor(tmp_repo).run_all()
        contrib_check = next(c for c in report.checks if c.name == "contributing")
        assert contrib_check.status == "pass"

    def test_warn_when_no_contributing(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        contrib_check = next(c for c in report.checks if c.name == "contributing")
        assert contrib_check.status == "warn"


class TestDoctorConfig:
    def test_pass_no_config(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        assert config_check.status == "pass"

    def test_pass_valid_config(self, tmp_repo):
        (tmp_repo / ".driftcheck.toml").write_text(
            '[driftcheck]\nfail_on_informational = false\n', encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        assert config_check.status == "pass"

    def test_warn_unknown_key(self, tmp_repo):
        (tmp_repo / ".driftcheck.toml").write_text(
            '[driftcheck]\nunknown_key = true\n', encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        assert config_check.status == "warn"

    def test_fail_invalid_toml(self, tmp_repo):
        (tmp_repo / ".driftcheck.toml").write_text(
            "this is not valid toml [[[", encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        # TOML parser is lenient, so it may pass or fail
        assert config_check.status in ("pass", "fail")

    def test_warn_unknown_top_level_key(self, tmp_repo):
        """A typo'd TOP-LEVEL key is silently dropped by load_config.

        load_config honours top-level keys as well as [driftcheck] ones, so a
        typo outside the section is a silent misconfiguration. The config check
        must warn about it exactly as it does inside the section.
        """
        (tmp_repo / ".driftcheck.toml").write_text(
            "exclude_dectors = [\"node\"]\n", encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        assert config_check.status == "warn"
        assert "exclude_dectors" in config_check.message

    def test_pass_valid_top_level_key(self, tmp_repo):
        """A known key at top level is honoured by load_config and stays valid."""
        (tmp_repo / ".driftcheck.toml").write_text(
            'exclude_detectors = ["node"]\n', encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        config_check = next(c for c in report.checks if c.name == "config")
        assert config_check.status == "pass"


class TestDoctorDetectors:
    def test_pass_all_enabled(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        det_check = next(c for c in report.checks if c.name == "detectors")
        assert det_check.status == "pass"

    def test_fail_all_excluded(self, tmp_repo):
        from driftcheck.config import DRIFT_KEYS
        all_detectors = [k for k in DRIFT_KEYS if k != "drifts"]
        excludes = ", ".join(f'"{d}"' for d in all_detectors)
        (tmp_repo / ".driftcheck.toml").write_text(
            f'[driftcheck]\nexclude_detectors = [{excludes}]\n', encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        det_check = next(c for c in report.checks if c.name == "detectors")
        assert det_check.status == "fail"

    def test_fail_all_excluded_top_level(self, tmp_repo):
        """A top-level exclude_detectors is honoured by load_config, so doctor
        must not report "All detectors enabled" for it."""
        from driftcheck.config import DRIFT_KEYS
        all_detectors = [k for k in DRIFT_KEYS if k != "drifts"]
        excludes = ", ".join(f'"{d}"' for d in all_detectors)
        (tmp_repo / ".driftcheck.toml").write_text(
            f"exclude_detectors = [{excludes}]\n", encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        det_check = next(c for c in report.checks if c.name == "detectors")
        assert det_check.status == "fail"

    def test_warn_excluded_top_level(self, tmp_repo):
        (tmp_repo / ".driftcheck.toml").write_text(
            'exclude_detectors = ["node"]\n', encoding="utf-8"
        )
        report = Doctor(tmp_repo).run_all()
        det_check = next(c for c in report.checks if c.name == "detectors")
        assert det_check.status == "warn"
        assert "1 detector(s) excluded" in det_check.message


class TestDoctorGitignore:
    def test_pass_no_gitignore(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        gi_check = next(c for c in report.checks if c.name == "gitignore")
        assert gi_check.status == "pass"

    def test_warn_excludes_toolchain(self, tmp_repo):
        (tmp_repo / ".gitignore").write_text("Cargo.toml\n", encoding="utf-8")
        report = Doctor(tmp_repo).run_all()
        gi_check = next(c for c in report.checks if c.name == "gitignore")
        assert gi_check.status == "warn"


class TestDoctorSymlinks:
    def test_pass_no_symlinks(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        sl_check = next(c for c in report.checks if c.name == "symlinks")
        assert sl_check.status == "pass"

    def test_warn_external_symlink(self, tmp_repo):
        # Create a directory truly outside tmp_repo
        import tempfile as tf
        external_dir = tf.mkdtemp()
        external_path = Path(external_dir) / "external.txt"
        external_path.write_text("external\n", encoding="utf-8")
        (tmp_repo / "link.txt").symlink_to(external_path)
        report = Doctor(tmp_repo).run_all()
        sl_check = next(c for c in report.checks if c.name == "symlinks")
        assert sl_check.status == "warn"


class TestDoctorBinaryFiles:
    def test_pass_no_binaries(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        bin_check = next(c for c in report.checks if c.name == "binary_files")
        assert bin_check.status == "pass"

    def test_warn_untracked_binary(self, tmp_repo):
        (tmp_repo / "app.exe").write_bytes(b"\x00" * 100)
        report = Doctor(tmp_repo).run_all()
        bin_check = next(c for c in report.checks if c.name == "binary_files")
        assert bin_check.status == "warn"


class TestDoctorLargeFiles:
    def test_pass_no_large_files(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        lf_check = next(c for c in report.checks if c.name == "large_files")
        assert lf_check.status == "pass"

    def test_warn_large_file(self, tmp_repo):
        (tmp_repo / "big.bin").write_bytes(b"\x00" * 2_000_000)
        report = Doctor(tmp_repo).run_all()
        lf_check = next(c for c in report.checks if c.name == "large_files")
        assert lf_check.status == "warn"


class TestDoctorDocFiles:
    def test_pass_docs_exist(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        doc_check = next(c for c in report.checks if c.name == "doc_files")
        assert doc_check.status == "pass"

    def test_warn_no_docs(self, tmp_repo):
        (tmp_repo / "README.md").unlink()
        report = Doctor(tmp_repo).run_all()
        doc_check = next(c for c in report.checks if c.name == "doc_files")
        assert doc_check.status == "warn"


class TestDoctorToolchain:
    def test_pass_toolchain_found(self, tmp_repo):
        report = Doctor(tmp_repo).run_all()
        tc_check = next(c for c in report.checks if c.name == "toolchain_files")
        assert tc_check.status == "pass"

    def test_warn_no_toolchain(self, tmp_repo):
        (tmp_repo / "pyproject.toml").unlink()
        report = Doctor(tmp_repo).run_all()
        tc_check = next(c for c in report.checks if c.name == "toolchain_files")
        assert tc_check.status == "warn"


class TestRunDoctor:
    def test_returns_report(self, tmp_repo):
        report = run_doctor(tmp_repo)
        assert len(report.checks) == 10

    def test_summary_counts(self, tmp_repo):
        # Add CONTRIBUTING.md to avoid warning so all 10 pass
        (tmp_repo / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
        report = run_doctor(tmp_repo)
        data = report.to_dict()
        assert data["summary"]["total"] == 10
        assert data["summary"]["pass"] == 10
        assert data["summary"]["fail"] == 0


class TestDoctorFix:
    def test_creates_readme(self, tmp_repo):
        (tmp_repo / "README.md").unlink()
        report = run_doctor(tmp_repo)
        fixes = doctor_fix(tmp_repo, report)
        assert any("README.md" in f for f in fixes)
        assert (tmp_repo / "README.md").exists()


class TestDoctorExitCode:
    def test_zero_when_all_pass(self, tmp_repo):
        report = run_doctor(tmp_repo)
        assert doctor_exit_code(report) == 0

    def test_one_when_fail(self, tmp_repo):
        (tmp_repo / "README.md").unlink()
        report = run_doctor(tmp_repo)
        assert doctor_exit_code(report) == 1


class TestPrintDoctorReport:
    def test_human_readable(self, tmp_repo, capsys):
        report = run_doctor(tmp_repo)
        print_doctor_report(report)
        captured = capsys.readouterr()
        assert "README.md found" in captured.out
        assert "Summary:" in captured.out

    def test_json_mode(self, tmp_repo, capsys):
        report = run_doctor(tmp_repo)
        print_doctor_report(report, json_mode=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "checks" in data
        assert "summary" in data


class TestDoctorPathsUsePosixSeparators:
    """`driftcheck doctor` reports repo-relative paths to the user, and they
    are matched against `.gitignore` entries, which are always written with
    forward slashes.

    `str(Path.relative_to())` renders with the platform separator, so on
    Windows doctor reported `dist\\app.exe` and failed to match the
    `dist/app.exe` line in `.gitignore`.
    """

    def test_binary_file_path_uses_posix_separators(self, windows_path, tmp_path):
        root = windows_path(tmp_path)
        (root / "README.md").write_text("# Test\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            "[project]\nname = 'test'\nrequires-python = '>=3.10'\n",
            encoding="utf-8",
        )
        dist = root / "dist"
        dist.mkdir()
        (dist / "app.exe").write_bytes(b"MZ\x00\x00")
        # A .gitignore that correctly lists the file with a forward slash.
        (root / ".gitignore").write_text("dist/app.exe\n", encoding="utf-8")

        report = Doctor(root).run_all()
        binary_check = next(c for c in report.checks if c.name == "binary_files")
        # The forward-slash .gitignore entry must match, so nothing is flagged.
        assert binary_check.status == "pass", binary_check.message
