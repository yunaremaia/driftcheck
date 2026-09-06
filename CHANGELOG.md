# Changelog

All notable changes to driftcheck will be documented in this file.

## [0.1.25] - 2026-09-06

### Added
- **Tool-versions (asdf/mise) drift detection**: `.tool-versions` file declares tool versions (node, python, go, rust, ruby, java, php, dotnet) — `driftcheck` now detects when README mentions a different version than what `.tool-versions` pins. Major.minor comparison (patch differences ignored).
- **NVMRC drift detection**: `.nvmrc` vs `package.json` engines.node — informational (non-blocking) check for Node.js version mismatches. Smart comparison: major-only versions (e.g., "20") match any version with the same major.
- **New CLI flags**:
  - `--list-detectors`: list all available detectors with blocking/informational status
  - `--only DETECTOR`: run only specified detectors (comma-separated)
  - `--exclude DETECTOR`: exclude specified detectors (comma-separated)
  - `--quiet` / `-q`: only output drifts, suppress OK messages
  - `--no-informational`: skip informational drifts in output
  - `--version`: show version and exit

### Fixed
- Duplicate `codecov/codecov-action` key in `actions.py` removed
- `__pycache__` files removed from git tracking; `.gitignore` improved

### Changed
- **CLI refactoring**: eliminated duplicated `drift_keys` list (4 copies → 1), centralizing all drift type metadata into a single `DETECTOR_INFO` registry for `--list-detectors`
- `tool_versions_drifts` is a blocking drift type; `nvmrc_drifts` is informational
- pyproject.toml classifiers updated

## [0.1.24] - 2026-09-06

### Added
- Lockfile drift detection: missing, stale, or orphaned lockfiles (package-lock.json, Cargo.lock, go.sum, Gemfile.lock, composer.lock)
- Lockfile drift is informational (non-blocking) — reported but doesn't fail the check

### Changed
- Bumped version to 0.1.24

## [0.1.23] - 2026-09-06

### Added
- PHP/Composer drift detection: `composer.json` `require.php` vs README mentions
- Bun drift detection: `package.json` `engines.bun` vs README mentions
- Line-ending drift now only fires when repo has source files (avoids noise on empty dirs)
- Dependabot and external-resource drifts are now informational (non-blocking) — reported but don't fail the check
- CLI now recognizes .NET, Ruby, Docker, and other project types beyond Rust/Node/Python/Go

### Fixed
- IndentationError in `find_lineending_drift` (stray `.replace()` call)
- CLI no longer treats dependabot/external-resource drifts as blocking failures
- Empty repos (no toolchain, no source files) correctly report "no toolchain version found"

## [0.1.22] - 2026-09-06

### Added
- Ruby version drift detection: `Gemfile` `ruby "x.y.z"` directive vs README mentions

## [0.1.21] - 2026-09-05

### Added
- .NET/C# version drift detection: `*.csproj` `<TargetFramework>` vs README mentions

## [0.1.20] - 2026-09-05

### Added
- GitHub Actions version drift auto-fix

## [0.1.19] - 2026-09-05

### Added
- CI OS drift detection: deprecated GitHub Actions runners

## [0.1.18] - 2026-09-04

### Added
- Dependabot drift detection: ecosystems used vs `.github/dependabot.yml` coverage

## [0.1.17] - 2026-09-04

### Added
- Docker Compose drift detection

## [0.1.16] - 2026-09-03

### Added
- Helm chart drift detection

## [0.1.15] - 2026-09-03

### Added
- Kubernetes manifest drift detection

## [0.1.14] - 2026-09-03

### Added
- GitHub Actions version drift detection

## [0.1.13] - 2026-09-02

### Added
- GitLab CI drift detection

## [0.1.12] - 2026-09-02

### Added
- CircleCI drift detection

## [0.1.11] - 2026-09-02

### Added
- Terraform provider version drift detection

## [0.1.10] - 2026-09-01

### Added
- Maven `pom.xml` Java version drift detection

## [0.1.9] - 2026-09-01

### Added
- Docker `FROM` tag drift detection
- Java/Gradle `sourceCompatibility` drift detection

## [0.1.8] - 2026-08-31

### Added
- External resource drift detection (offline/air-gapped HTML rendering)

## [0.1.7] - 2026-08-30

### Added
- GitHub Actions Node 20 → Node 24 migration drift detection

## [0.1.6] - 2026-08-29

### Added
- Skills directory count drift detection

## [0.1.5] - 2026-08-28

### Added
- Line-ending drift detection (`.gitattributes` CRLF safety)

## [0.1.4] - 2026-08-27

### Added
- Go version drift detection (`go.mod` vs README)

## [0.1.3] - 2026-08-27

### Added
- Python version drift detection (`pyproject.toml` vs README)

## [0.1.2] - 2026-08-26

### Added
- Node.js version drift detection (`package.json` engines vs README)

## [0.1.1] - 2026-08-26

### Added
- Rust version drift detection with Cargo.toml `rust-version` support

## [0.1.0] - 2026-08-26

### Initial release
- Rust toolchain drift detection (`rust-toolchain.toml` vs README)
- `--fix` auto-correction flag
- `--json` machine-readable output
