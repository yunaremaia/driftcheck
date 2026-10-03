# Changelog

All notable changes to driftcheck will be documented in this file.

## [Unreleased]

### Fixed

- **SARIF output no longer silently drops detectors.** 17 detectors were detected and
  printed normally but never reached `--sarif` output, because `to_sarif` gates on two
  independent structures — the `drift_keys` list it walks and the `DRIFT_RULES` mapping it
  looks up — and a key missing from either is skipped without any warning. This affected 9
  externally contributed detectors (`package_version`, `pyproject_tool`, `python_req`,
  `justfile`, `terraform_lock`, `r`, `go_replace`, `frontmatter`, `helm_dependency`) whose
  rule wiring was lost in a rebase, plus `git_submodule`, `a2a`, `changelog`,
  `dockerfile_instruction`, `freshness`, `kmp`, `python_version_file` and `scala`.
- **`git_submodule_drifts` rule was malformed.** It was a 2-tuple while the rest are
  3-tuples `(rule_id, name, description)`, so its rule id and name could not be unpacked
  consistently with every other rule.
- Added `tests/test_sarif_coverage.py`, which asserts every drift key emitted by
  `detector.py` is reachable in SARIF and that every rule is a well-formed 3-tuple, so a
  detector added without its SARIF wiring now fails the suite instead of disappearing from
  Code Scanning.

### Changed

- **Lint gate over `tests/` narrowed to `F821` instead of dropped entirely.** `tests/`
  stays out of the pyflakes (`F`) gate, so that gate still cannot pressure a change into
  weakening or deleting a test. It gains one narrower rule, `F821` (undefined name),
  because an undefined name is a `NameError` the moment the line runs rather than a style
  opinion — so this rule cannot be satisfied by touching a test. The rest of pyflakes over
  `tests/` stays ungated; the measured remainder is recorded in BACKLOG.md.

- Removed 6 redundant in-function reimports in `tests/` (`test_deno.py`,
  `test_detector.py`, `test_plugin_sandbox.py`) that shadowed a module-scope import of the
  same name.

### Fixed

- **`tests/test_version.py` raised `NameError` instead of skipping.** The test called
  `pytest.skip()` but the module never imported `pytest`, so on any machine where the
  distribution metadata resolves to the `0.0.0.dev0` dev placeholder — a plain source
  checkout, i.e. any local dev run without `pip install -e .` — pytest reported the test
  as **failed** with `NameError: name 'pytest' is not defined` rather than skipping it.
  CI never saw it because CI installs the package, so the branch that skips was never
  taken there. Now verified to skip correctly with the package absent.

## [0.1.47] - 2026-10-01

84 commits since 0.1.46. Highlights below; see the git history for the full list.

### Added

**New detectors**

- **npm workspace dependency ranges** (`npm_workspace_drifts`): the same dependency declared at
  different version ranges across workspace `package.json` files
- **Cargo features** (`cargo_feature_drifts`): `Cargo.toml` `[features]` vs explicit
  `features = [...]` lists and `--features` flags in docs
- **A2A (Agent2Agent) protocol** (`a2a_drifts`, informational): agent card `spec_version`,
  capabilities and endpoints vs docs. Cross-platform `.a2a/` card discovery
- **Python version drift** (`python_version_drifts`): unified detector for `.python-version`,
  `requires-python` and README mentions
- **Git submodule commits** (`git_submodule_drifts`): pinned submodule SHA vs docs
- **`[tool.*]` config drift** (`pyproject_tool_drifts`): `[tool.ruff]`, `[tool.black]`,
  `[tool.mypy]`, `[tool.pyright]` targets vs `requires-python`
- **Python requirements** (`python_req_drifts`) and **legacy setup** (`python_setup_drifts`):
  `requirements.txt` pins and `setup.py`/`setup.cfg` vs docs
- **Justfile**: recipe/declaration drift in `justfile`
- **Terraform lock** (`terraform_lock_drifts`): `.terraform.lock.hcl` provider versions vs docs
- **R** (`r_drifts`): R version declarations (DESCRIPTION / renv) vs docs
- **Go replace directives** (`go_replace_drifts`): `replace` entries in `go.mod` vs docs
- **Frontmatter** (`frontmatter_drifts`): version claims in Markdown frontmatter
- **Helm dependencies** (`helm_dependency_drifts`): `Chart.yaml` dependencies vs docs
- **Julia** (`julia_drifts`): `Project.toml` compat bounds vs docs
- **Changelog** (`changelog_drifts`), **Python freshness** (`freshness_drifts`) and
  **uv.lock** detectors
- **GitHub Actions version drift** (`actions_drifts`): action version references in docs

**CLI and features**

- **`driftcheck --explain`**: explains why a drift was detected (file, line, values, diff,
  impact, fix suggestion)
  - `--explain <detector:file>`, `--explain-all`, `--explain-format json|text`, `--explain-fix`
- **`driftcheck --baseline`**: incremental drift detection — accept current state as known good
  and report only NEW drifts
  - `--baseline`, `--baseline-update`, `--baseline-reset`, `--baseline-show`
  - Pre-existing drifts become warnings; `_baseline` metadata in JSON, properties in SARIF
- **`driftcheck doctor`**: repository diagnostics (fixes #268)
- **`driftcheck init`**: auto-detects project type and generates `.driftcheck.toml`
  (detects 30+ project types; `--force`, `--dry-run`)
- **Pre-commit staged-only mode** (#285)
- **`package.json` version drift**: `version` vs badge URLs, install commands, changelog headers
- **`package-lock` dependency resolution validation** (#286)
- **`.driftcheck.toml` validation** with strict mode
- **`--fail-on-informational`** flag and matching config option (#144)
- **Configurable parallel read timeouts** (#238)
- **Max file size OOM protection** (`max_file_size`, #150)
- **CRLF/LF line-ending drift** vs `.gitattributes` policy (#216)

### Fixed

- `_print_blocking_drifts` now handles all drift types (#233)
- External CDN detection reports all CDN references per file, not just the first (#228)
- Symlink loop handling in `_walk_files` and prefix-collision symlink bypass in `_safe_glob`
- Replaced the hand-rolled TOML parser with `tomllib` (`tomli` backport on Python 3.10) —
  inline comments, multi-line arrays and `#` inside quoted strings now parse correctly,
  and a malformed `.driftcheck.toml` reports an error instead of silently applying a
  half-parsed config (#143, #151). See the correction note below.
- Replaced bare `except` with specific exceptions in detectors and `cli.py` (#309)
- Wired `custom_detectors` config into `scan_repo` (#209)
- Duplicate `git_tag_drifts` key in `DRIFT_RULES` (#298)
- SARIF: URI-encoded file paths in `artifactLocation.uri` (#230), repo root URI base IDs (#282),
  rule metadata for 7 newer detectors (#145)
- Scala, changelog and freshness detectors registered in `scan_repo` and the CLI
- All new detectors registered in `scan_repo` with proper file reading
- Git-mode returns an empty set when there are no changed files
- Windows compatibility: `tmp_path` instead of hardcoded `/tmp/`, cross-platform path handling

### Documentation

- Added `SECURITY.md` and `SUPPORT.md`
- Added GitHub Stars badge
- Resolved an unreconciled merge conflict block committed in README.md and docs/detectors.md
- Repaired 4 malformed rows in the README detector comparison matrix
- Removed a `rust_workspace.py` entry from MANIFEST.md — no such detector module exists

### Changed

- Removed the legacy `"drifts"` alias (#146)
- Removed the dead `_read_files_parallel` helper and its now-unused
  `ThreadPoolExecutor` imports; the function had no callers in `src/` or `tests/` (#147)

### Correction notes

- **`070dccc` ("replace hand-rolled TOML parser with tomllib", #151) was an empty commit.**
  Its message and the entry in `MANIFEST.md` claimed it replaced `_parse_toml`, but the
  commit changed no files and `_parse_toml` remained the hand-rolled parser. The
  replacement actually landed later, together with the dead-code removal above; the
  "Fixed" entry above now describes the shipped state rather than `070dccc`.
- **`dffd414` (#147) removed only the `"drifts"` alias.** `_read_files_parallel` was
  still present and still uncalled, so the earlier "Removed ... dead
  `_read_files_parallel` (#146, #147)" entry did not match the tree either.

## [0.1.46] - 2026-09-18

### Added
- **`driftcheck init` subcommand**: auto-detects project type and generates `.driftcheck.toml` config
  - Detects 30+ project types (Rust, Node, Python, Go, Docker, Java, etc.)
  - Enables relevant detectors based on project files
  - `--force` to overwrite existing config
  - `--dry-run` to preview without writing
  - Lists detected project files and enabled detectors in config comments

## [Unreleased]

### Added
- **Kotlin Multiplatform (KMP) drift detection**: detects version mismatch between `gradle/libs.versions.toml` KMP version catalog and README badges/mentions for Kotlin, Compose, Coroutines, KGP, AGP, KSP
  - Parses `[versions]` and `[plugins]` sections of TOML catalog
  - Compares against badge URLs (shields.io) and prose mentions
  - Minor/patch tolerance for Kotlin, exact match for Compose BOM
  - 24 new tests, 1170 total

### Fixed
- **Nix flake.lock drift detection**: detects version mismatch between `flake.lock` nixpkgs pins and README mentions
  - Parses `flake.lock` JSON structure and extracts nixpkgs/nixos version pins
  - Matches against README patterns like `nixpkgs 24.05`, `nixos-24.05`, `nixpkgs-unstable`
  - Handles multiple nixpkgs inputs (stable + unstable) with channel-aware comparison
  - 9 new tests, 1010 total

### Fixed
- Synced README and docs stats: 59 detector modules, 67 registered detectors, 1001 tests

## [0.1.44] - 2026-09-12

### Added
- **Typosquat drift detection**: flags suspiciously-named dependencies in lockfiles (`requirements.txt`, `package.json`, `Cargo.toml`) by comparing against curated known-package lists for PyPI, npm, and crates ecosystems
  - Uses edit-distance-2 heuristic with proportional length thresholds to minimize false positives
  - Bridges into `taintrace`'s security-focused detection from driftcheck's scanning pipeline
  - 17 new tests, 1001 total

### Changed
- Bumped version to 0.1.44
- Updated README test count to 1001

## [0.1.43] - 2026-09-12

### Added
- **Dockerfile base image drift detection**: flags floating tags (`:latest`, `:stable`, `:nightly`, no tag) and sibling Dockerfile drift (e.g., `Dockerfile.dev` pins `node:18` while `Dockerfile.prod` pins `node:20`)
  - 14 new tests, 984 total

### Changed
- Bumped version to 0.1.43

## [0.1.42] - 2026-09-12

### Added
- **Engines drift detection**: `package.json` `engines.node` vs `.nvmrc` and `volta.node` — detects when Node.js version constraints conflict across files
  - Supports semver prefixes (`>=`, `^`, `~`, `v`) and LTS aliases
  - 24 new tests, 970 total

### Changed
- Bumped version to 0.1.42

## [0.1.41] - 2026-09-11

### Added
- **Mise.toml drift detection**: `mise.toml` `[tools]` section vs README mentions — detects when README references a version that doesn't match `mise.toml`
  - Supports plain string specs (`node = "22"`) and dict specs (`python = {version = "3.12"}`)
  - 12 new tests, 946 total

### Changed
- Bumped version to 0.1.41
- Synced README stats: 52 modules, 60 detectors, 946 tests

## [0.1.40] - 2026-09-11

### Fixed
- **SARIF**: added missing `devcontainer_drifts`, `compose_override_drifts`, `helm_values_drifts` to `DRIFT_RULES`, `drift_keys`, and `_drift_message` — these three detectors now produce valid SARIF output for GitHub Code Scanning
- **SARIF**: `to_sarif()` now auto-detects package `__version__` when `version=None` (was hardcoded `0.1.24`)
- **git_mode**: added `devcontainer_drifts` to `DETECTOR_FILE_PATTERNS` so devcontainer.json changes trigger the detector in incremental mode
- Synced README stats: 50 modules, 53 detectors, 928 tests

### Tests
- Added `test_sarif_new_types.py` (6 tests) covering new SARIF drift types and version auto-detection

## [0.1.39] - 2026-09-11

### Fixed
- Synced `__version__` in `src/driftcheck/__init__.py` to `0.1.39` (was `0.1.38`) — CLI `--version` and SARIF output now match `pyproject.toml`
- Updated README stats: 50 detectors (was 49)

### Changed
- Merged combined test files into individual detector test files (elixir_cmake, maven_terraform_java removed)
- Each detector now has its own test file with no duplicates
- Bumped version to 0.1.39

## [0.1.38] - 2026-09-11

### Added
- **Git Tag drift detection**: latest git tag vs README version mentions — detects when README references a stale version
- SARIF rule `git-tag-drift` (informational level)
- New tests: `test_git_tag.py` (11 tests), `test_fix.py` (17 tests)

### Fixed
- Restored `get_latest_git_tag` and `find_git_tag_drift` to `detectors/__init__.py` (were accidentally removed)
- Added missing exports to `__all__`: `get_latest_git_tag`, `find_git_tag_drift`, `parse_semver`, `SEMVER_RE`

### Changed
- Bumped version to 0.1.38
- Updated README stats: 49 detectors, 915 tests

## [0.1.37] - 2026-09-09

### Added
- **Taskfile drift detection**: `Taskfile.yml` tasks vs `Makefile` targets — detects tasks defined in Taskfile but missing from Makefile, and vice versa
- SARIF rule `taskfile-drift` (blocking level)
- New tests: `test_taskfile.py` (17 tests)

### Changed
- Bumped version to 0.1.37
- 48 detectors total, 887 tests total

## [0.1.36] - 2026-09-09

### Added
- **NPMRC drift detection**: `.npmrc` registry vs README mentions — detects when README references a different registry than what `.npmrc` configures
- **Yarn RC drift detection**: `.yml` Yarn version vs README mentions — handles both `yarnPath` and `yarnVersion` fields
- **PNPM workspace drift detection**: `pnpm-workspace.yaml` packages vs `package.json` workspaces — catches mismatches between the two workspace definitions
- SARIF rules for all 3 new detectors: `npmrc-registry-drift`, `yarnrc-version-drift`, `pnpm-workspace-drift`
- New tests: `test_npmrc.py` (9 tests), `test_yarnrc.py` (12 tests), `test_pnpm.py` (12 tests)

### Changed
- Bumped version to 0.1.36
- 43 detectors total, 423 tests total

## [0.1.35] - 2026-09-09

### Added
- **Version file drift detection**: `.ruby-version`, `.python-version`, `.node-version`, `.java-version`, `.terraform-version` vs README mentions — major.minor comparison (patch differences ignored)
- SARIF rules for all 5 version file types (blocking level)
- New tests: `test_version_files.py` (21 tests)

### Changed
- Bumped version to 0.1.35

## [0.1.34] - 2026-09-08

### Added
- **Jenkins drift detection**: `Jenkinsfile` tool versions (`nodejs`, `python`, `docker.image`) vs README mentions — major.minor comparison (patch differences ignored)
- SARIF rule `jenkins-version-drift` (blocking level)
- New tests: `test_jenkins.py` (16 tests)

### Changed
- Bumped version to 0.1.34

## [0.1.33] - 2026-09-07

### Changed
- README: listed Jenkins as planned detector (implemented in v0.1.34)

## [0.1.32] - 2026-09-07

### Added
- SARIF rules for all v0.1.32 detectors: `requirements-version-drift`, `kotlin-version-drift`, `pipfile-version-drift`, `conda-unpinned-drift`
- SARIF message formatting for requirements, kotlin, pipfile, and conda drifts
- Tests: 5 new SARIF tests for the v0.1.32 drift types

### Fixed
- Fixed unterminated string literal in `test_detector.py` (Pipfile JSON test data)
- Added missing imports (`find_pipfile_drift`, `find_conda_drift`) to `test_detector.py`

### Changed
- Bumped version to 0.1.32 (aligned `__init__.py` with `pyproject.toml`)

## [0.1.31] - 2026-09-07

### Added
- **Elixir drift detection**: `mix.exs` `elixir: "~> X.Y"` directive vs README mentions — major.minor comparison (patch differences ignored)
- **CMake drift detection**: `CMakeLists.txt` `cmake_minimum_required(VERSION X.Y)` vs README mentions — major.minor comparison (patch differences ignored)
- **Git-mode scanning** (`--git-mode`): incremental drift detection that only scans files changed since a base commit (default: HEAD~1). Uses `git diff --name-only` + `git ls-files --others` for CI/PR filtering
- SARIF rules `elixir-version-drift` and `cmake-version-drift` (blocking level)
- New tests: `test_elixir.py` (9 tests), `test_cmake.py` (7 tests), `test_git_mode.py` (15 tests)

### Fixed
- Restored `toolchain_version` to scan result dict (was accidentally removed in v0.1.30 WIP)
- Added missing `elixir_drifts` and `cmake_drifts` entries to result dict
- Fixed syntax error in `other_indicators` list (missing `]`)

### Changed
- Bumped version to 0.1.31
- `DETECTOR_FILE_PATTERNS` mapping now includes `elixir_drifts` and `cmake_drifts` for git-mode filtering

## [0.1.30] - 2026-09-07

### Added
- Environment drift detection: `.env.example` vs `.env` (missing/extra keys), `docker-compose.yml` vs `docker-compose.prod.yml` (image tag differences), `values.yaml` vs `values.prod.yaml` (Helm value differences for `replicaCount`, `tag`, `repository`, `resources`)

## [0.1.29] - 2026-09-07

### Added
- **Makefile drift detection**: detects when tool versions in Makefile variables (`GCC_VERSION`, `CMAKE_VERSION`, `GO_VERSION`, etc.) or assignments (`CC = gcc-13`, `GO = 1.22`) differ from README mentions. Major.minor comparison (patch differences ignored). Supports recursive glob for `make/*.mk`.
- **GitHub Action** (`action.yml`): add driftcheck to CI with a single `uses: yunaremaia/driftcheck@main` step. Supports `fail-on-drift`, `args`, and SARIF upload via `sarif: true`.
- **Markdown reports** (`--report`): outputs a formatted markdown summary for CI job summaries or PR comments.
- **Config initialization** (`--init`): generates a `.driftcheck.toml` file with commented examples.
- SARIF rule `makefile-version-drift` (blocking level)

### Changed
- Updated README with GitHub Action and `--report`/`--init` sections
- Bumped version to 0.1.29

## [0.1.28] - 2026-09-06

### Added
- **Dart/Flutter drift detection**: `pubspec.yaml` `environment.sdk` constraint vs README mentions — major.minor comparison (patch differences ignored). Handles `>=X.Y.Z <A.B.C`, `^X.Y.Z`, and exact constraints. Intentionally excludes Flutter release versions (independent of Dart SDK).
- **Plugin system**: load custom detectors from `.driftcheck_plugins/` directory. Plugins define a `register()` function returning `{name: detector_fn}`. Each detector_fn takes `(root: Path, docs: dict[str, str]) -> list[dict]`. Plugin results appear as `plugin_<name>_drifts` in output. Broken plugins are skipped with a warning.
- SARIF rule `dart-sdk-version-drift` (blocking level)

### Changed
- Bumped version to 0.1.28

## [0.1.27] - 2026-09-06

### Added
- **Deno drift detection**: `deno.json` / `deno.jsonc` `version` field vs README mentions — major.minor comparison (patch differences ignored)
- **Configuration file support**: `.driftcheck.toml` in repo root to customize detection behavior
  - `exclude_detectors`: list of detectors to skip (supports short names like "rust" or drift keys like "node_drifts")
  - `fail_on_informational`: treat informational drifts as blocking
  - `ignore_patterns`: patterns to ignore in drift detection
- **Pre-commit hook**: `.pre-commit-hooks.yaml` for use with pre-commit framework
- SARIF rule `deno-version-drift` (blocking level)

### Fixed
- Fixed dead code in `scan_repo()` where exclusion filter was placed after `return` statement (unreachable)
- Aligned `__version__` in `__init__.py` with `pyproject.toml` (0.1.27)

### Changed
- Bumped version to 0.1.27

## [0.1.26] - 2026-09-06

### Added
- **Swift Package Manager drift detection**: `Package.swift` `swift-tools-version` and dependency version pins vs README mentions. Major.minor comparison (patch differences ignored).
- SARIF rule `swift-package-version-drift` (blocking level)

### Changed
- Bumped version to 0.1.26

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
