"""driftcheck doctor — repository diagnostics command.

Provides comprehensive pre-scan diagnostics to catch common misconfigurations
that cause confusing scan results.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG, load_config


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: str  # "pass", "fail", "warn"
    message: str
    fixable: bool = False
    fix_hint: str = ""


@dataclass
class DoctorReport:
    """Aggregated diagnostic report."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "warn"]

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "pass"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "fixable": c.fixable,
                    "fix_hint": c.fix_hint,
                }
                for c in self.checks
            ],
            "summary": {
                "total": len(self.checks),
                "pass": len(self.passed),
                "fail": len(self.failed),
                "warn": len(self.warnings),
            },
        }


class Doctor:
    """Run diagnostic checks on a repository."""

    def __init__(self, root: Path):
        self.root = root

    def run_all(self) -> DoctorReport:
        """Run all diagnostic checks and return a report."""
        checks: list[CheckResult] = []
        checks.append(self.check_readme())
        checks.append(self.check_contributing())
        checks.append(self.check_config())
        checks.append(self.check_detectors())
        checks.append(self.check_gitignore())
        checks.append(self.check_symlinks())
        checks.append(self.check_binary_files())
        checks.append(self.check_large_files())
        checks.append(self.check_doc_files())
        checks.append(self.check_toolchain_files())
        return DoctorReport(checks=checks)

    def check_readme(self) -> CheckResult:
        """Check that at least one README file exists."""
        for pattern in ["README.md", "README.rst", "README.txt", "README"]:
            if (self.root / pattern).exists():
                return CheckResult(
                    name="readme",
                    status="pass",
                    message=f"{pattern} found",
                )
        return CheckResult(
            name="readme",
            status="fail",
            message="No README file found (expected README.md, README.rst, or README.txt)",
            fixable=True,
            fix_hint="Create a README.md with project documentation",
        )

    def check_contributing(self) -> CheckResult:
        """Check that a CONTRIBUTING file exists."""
        for pattern in ["CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING"]:
            if (self.root / pattern).exists():
                return CheckResult(
                    name="contributing",
                    status="pass",
                    message=f"{pattern} found",
                )
        return CheckResult(
            name="contributing",
            status="warn",
            message="No CONTRIBUTING.md found",
            fixable=True,
            fix_hint="Create CONTRIBUTING.md with contribution guidelines",
        )

    def check_config(self) -> CheckResult:
        """Check that .driftcheck.toml is valid (if present)."""
        config_path = self.root / ".driftcheck.toml"
        if not config_path.exists():
            return CheckResult(
                name="config",
                status="pass",
                message="No .driftcheck.toml (using defaults)",
            )
        try:
            # Read through load_config, the single source of truth for how
            # .driftcheck.toml is interpreted. These checks used to re-parse
            # the TOML and look only inside [driftcheck], so every top-level
            # key -- which load_config honours too (config.py) -- was invisible
            # here: a top-level typo was reported as ".driftcheck.toml is
            # valid" while the real key was silently dropped, and a top-level
            # exclude_detectors was reported as "All detectors enabled" on a
            # scan that was in fact running with detectors excluded.
            cfg = load_config(self.root)
            # Foreign tables ([tool.foo] and friends) are dropped by
            # load_config, so what remains is driftcheck's own key set.
            unknown = set(cfg) - set(DEFAULT_CONFIG)
            if unknown:
                return CheckResult(
                    name="config",
                    status="warn",
                    message=f".driftcheck.toml has unknown keys: {', '.join(sorted(unknown))}",
                )
            return CheckResult(
                name="config",
                status="pass",
                message=".driftcheck.toml is valid",
            )
        except Exception as e:
            return CheckResult(
                name="config",
                status="fail",
                message=f".driftcheck.toml parse error: {e}",
            )

    def check_detectors(self) -> CheckResult:
        """Check that not all detectors are excluded."""
        config_path = self.root / ".driftcheck.toml"
        if not config_path.exists():
            return CheckResult(
                name="detectors",
                status="pass",
                message="No config — all detectors enabled",
            )
        try:
            # Same reasoning as check_config: go through load_config so the
            # exclusions counted here are the ones the scan actually applies.
            excluded = load_config(self.root).get("exclude_detectors", [])
            if not isinstance(excluded, list):
                return CheckResult(
                    name="detectors",
                    status="warn",
                    message="exclude_detectors is not a list",
                )
            from .config import DRIFT_KEYS
            all_detectors = [k for k in DRIFT_KEYS if k != "drifts"]
            if len(excluded) >= len(all_detectors):
                return CheckResult(
                    name="detectors",
                    status="fail",
                    message=f"All {len(all_detectors)} detectors are excluded — scan will be empty",
                    fixable=True,
                    fix_hint="Remove some entries from exclude_detectors",
                )
            if excluded:
                return CheckResult(
                    name="detectors",
                    status="warn",
                    message=f"{len(excluded)} detector(s) excluded",
                )
            return CheckResult(
                name="detectors",
                status="pass",
                message="All detectors enabled",
            )
        except Exception as e:
            return CheckResult(
                name="detectors",
                status="warn",
                message=f"Could not verify detectors: {e}",
            )

    def check_gitignore(self) -> CheckResult:
        """Check for .gitignore patterns that may exclude toolchain files."""
        gitignore_path = self.root / ".gitignore"
        if not gitignore_path.exists():
            return CheckResult(
                name="gitignore",
                status="pass",
                message="No .gitignore (OK for small repos)",
            )
        try:
            text = gitignore_path.read_text(encoding="utf-8")
            suspicious = []
            tool_patterns = ["Cargo.toml", "package.json", "go.mod", "pyproject.toml",
                             "Dockerfile", "*.toml", "*.lock"]
            for pattern in tool_patterns:
                if pattern in text:
                    suspicious.append(pattern)
            if suspicious:
                return CheckResult(
                    name="gitignore",
                    status="warn",
                    message=f".gitignore may exclude toolchain files: {', '.join(suspicious)}",
                )
            return CheckResult(
                name="gitignore",
                status="pass",
                message=".gitignore does not exclude toolchain files",
            )
        except Exception as e:
            return CheckResult(
                name="gitignore",
                status="warn",
                message=f"Could not read .gitignore: {e}",
            )

    def check_symlinks(self) -> CheckResult:
        """Check for symlinks pointing outside repo root."""
        external_symlinks = []
        try:
            for path in self.root.rglob("*"):
                if path.is_symlink():
                    try:
                        resolved = path.resolve()
                        if not str(resolved).startswith(str(self.root.resolve())):
                            external_symlinks.append(path.relative_to(self.root).as_posix())
                    except OSError:
                        external_symlinks.append(path.relative_to(self.root).as_posix())
        except OSError:
            pass
        if external_symlinks:
            examples = ", ".join(external_symlinks[:3])
            return CheckResult(
                name="symlinks",
                status="warn",
                message=f"{len(external_symlinks)} external symlink(s): {examples}",
                fix_hint="Set follow_symlinks=false to skip these during scan",
            )
        return CheckResult(
            name="symlinks",
            status="pass",
            message="No external symlinks found",
        )

    def check_binary_files(self) -> CheckResult:
        """Check for binary files that should be in .gitignore."""
        binary_extensions = {".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".class"}
        binaries = []
        gitignore_path = self.root / ".gitignore"
        gitignore_text = ""
        if gitignore_path.exists():
            try:
                gitignore_text = gitignore_path.read_text(encoding="utf-8")
            except OSError:
                pass
        try:
            for path in self.root.rglob("*"):
                if path.is_file() and path.suffix in binary_extensions:
                    rel = path.relative_to(self.root).as_posix()
                    if rel not in gitignore_text:
                        binaries.append(rel)
        except OSError:
            pass
        if binaries:
            return CheckResult(
                name="binary_files",
                status="warn",
                message=f"{len(binaries)} untracked binary file(s): {', '.join(binaries[:3])}",
                fixable=True,
                fix_hint="Add binary file patterns to .gitignore",
            )
        return CheckResult(
            name="binary_files",
            status="pass",
            message="No untracked binary files found",
        )

    def check_large_files(self) -> CheckResult:
        """Check for files larger than default max_file_size."""
        max_size = 1_000_000  # 1MB default
        large_files = []
        try:
            for path in self.root.rglob("*"):
                if path.is_file():
                    try:
                        if path.stat().st_size > max_size:
                            size_mb = path.stat().st_size / 1_000_000
                            large_files.append(f"{path.relative_to(self.root).as_posix()} ({size_mb:.1f}MB)")
                    except OSError:
                        pass
        except OSError:
            pass
        if large_files:
            examples = ", ".join(large_files[:3])
            return CheckResult(
                name="large_files",
                status="warn",
                message=f"{len(large_files)} large file(s) >1MB will be skipped: {examples}",
                fix_hint="Increase max_file_size in .driftcheck.toml if needed",
            )
        return CheckResult(
            name="large_files",
            status="pass",
            message="No large files found",
        )

    def check_doc_files(self) -> CheckResult:
        """Check for documentation files to scan."""
        doc_files = []
        for pattern in ["README.md", "CONTRIBUTING.md", "docs/", "doc/"]:
            if pattern.endswith("/"):
                if (self.root / pattern).is_dir():
                    doc_files.append(pattern)
            elif (self.root / pattern).exists():
                doc_files.append(pattern)
        if doc_files:
            return CheckResult(
                name="doc_files",
                status="pass",
                message=f"Doc files found: {', '.join(doc_files)}",
            )
        return CheckResult(
            name="doc_files",
            status="warn",
            message="No documentation files found to scan",
            fixable=True,
            fix_hint="Create README.md or specify doc_paths in .driftcheck.toml",
        )

    def check_toolchain_files(self) -> CheckResult:
        """Check for toolchain/manifest files."""
        toolchain_patterns = [
            "Cargo.toml", "package.json", "go.mod", "pyproject.toml",
            "requirements.txt", "Dockerfile", "build.gradle", "pom.xml",
            "Gemfile", "composer.json",
        ]
        found = []
        for pattern in toolchain_patterns:
            matches = list(self.root.glob(pattern))
            if matches:
                found.append(pattern)
        if found:
            return CheckResult(
                name="toolchain_files",
                status="pass",
                message=f"Toolchain files found: {', '.join(found[:5])}",
            )
        return CheckResult(
            name="toolchain_files",
            status="warn",
            message="No toolchain or manifest files found — scan may be empty",
        )


def run_doctor(root: Path) -> DoctorReport:
    """Convenience: run all diagnostics and return the report."""
    return Doctor(root).run_all()


def print_doctor_report(report: DoctorReport, json_mode: bool = False) -> None:
    """Print the doctor report to stdout."""
    if json_mode:
        print(json.dumps(report.to_dict(), indent=2))
        return

    for check in report.checks:
        icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(check.status, "?")
        line = f"  {icon} [{check.status.upper():4s}] {check.name}: {check.message}"
        print(line)
        if check.fixable and check.fix_hint:
            print(f"      → {check.fix_hint}")

    summary = report.to_dict()["summary"]
    print()
    print(f"Summary: {summary['pass']} passed, {summary['fail']} failed, {summary['warn']} warned")


def doctor_exit_code(report: DoctorReport) -> int:
    """Determine exit code from report: 0=pass, 1=fail, 2=error."""
    if any(c.status == "fail" for c in report.checks):
        return 1
    return 0


def doctor_fix(root: Path, report: DoctorReport) -> list[str]:
    """Attempt to auto-fix fixable issues. Returns list of fixes applied."""
    fixes = []
    for check in report.checks:
        if not check.fixable or check.status == "pass":
            continue
        if check.name == "readme":
            readme_path = root / "README.md"
            readme_path.write_text("# Project\n\n", encoding="utf-8")
            fixes.append("Created README.md")
        elif check.name == "binary_files":
            gitignore_path = root / ".gitignore"
            try:
                existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
                with gitignore_path.open("a", encoding="utf-8") as f:
                    if not existing.endswith("\n"):
                        f.write("\n")
                    f.write("# Auto-added by driftcheck doctor\n*.exe\n*.dll\n*.so\n*.dylib\n*.bin\n*.o\n*.a\n*.class\n")
                fixes.append("Added binary patterns to .gitignore")
            except OSError:
                pass
        elif check.name == "detectors":
            # Can't safely auto-fix this — would require understanding intent
            pass
    return fixes
