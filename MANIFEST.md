# Driftcheck Manifest — v0.1.46

## Core Stats
- **64 detector modules** (files in `src/driftcheck/detectors/` excluding `__init__.py`)
- **68 registered detectors** (DRIFT_KEYS in `src/driftcheck/config.py`)
- **68 find_* functions** exported from top-level `__init__.py` (plus `to_sarif`)
- **1276 tests** with >95% code coverage
- **SARIF 2.1.0** output for GitHub Code Scanning

## Recent Commits
- `c3100f5` Merge PR #203: feat(sarif): add originalUriBaseIds for GitHub Code Scanning file links (fixes #193)
- `17c5eeb` Merge PR #179: fix(detector): log file read failures in _read_files_parallel (closes #178)
- `fe85a32` fix(detector): log file read failures in _read_files_parallel (closes #178)
- `e95f830` fix: resolve all ruff linting errors (183 → 0) to fix PR #160 CI (#165)
- `a845826` docs: correct registered detector count from 67 to 83
- `1750b51` docs: correct MANIFEST.md counts (v0.1.46, 64 find_* funcs, 1200 tests)
- `e56dacb` fix(sarif): replace stale 0.1.40 fallback with 'unknown' (fixes #162) (#166)
- `6736634` fix: replace hand-rolled TOML parser with tomllib (fixes #151) (#157)
- `dffd414` refactor: remove legacy "drifts" alias and dead _read_files_parallel (fixes #146, #147)
- `c625cef` fix(sarif): add rule metadata for 7 newer detectors (fixes #145)
- `e56dacb` feat: add max_file_size OOM protection (fixes #150) (#153)
- `578e826` feat: add driftcheck init subcommand with auto-detection (fixes #134) (#142)
- `ef24f7f` Merge PR #138 from yunaremaia/fix/sarif-absolute-paths-leak

## Note on Count
**64 detector module files** in `src/driftcheck/detectors/` (excluding `__init__.py`, which is the package init). All counts verified against the codebase on 2026-09-19 (commit `c3100f5`).

## Detectors Documented in README "Checks" Section
All 64 detector modules are documented in the README "Checks" section, though some use display names that differ from the file names:

| File | README Display Name |
|------|---------------------|
| `actions.py` | GitHub Actions |
| `bazel.py` | Bazel |
| `bun.py` | Bun |
| `ci_os.py` | CI OS |
| `circleci.py` | CircleCI |
| `cmake.py` | CMake |
| `compose.py` | Docker Compose |
| `conda.py` | Conda |
| `count.py` | Count |
| `dart.py` | Dart/Flutter |
| `deno.py` | Deno |
| `dependabot.py` | Dependabot |
| `devcontainer.py` | Devcontainer |
| `docker.py` | Docker |
| `docker_bases.py` | (part of Docker) |
| `docker_multistage.py` | (part of Docker) |
| `dockerfile_instructions.py` | Dockerfile Instructions |
| `dotnet.py` | .NET/C# |
| `editorconfig.py` | EditorConfig |
| `elixir.py` | Elixir |
| `engines.py` | (part of Node) |
| `env_drift.py` | Environment drift |
| `external.py` | External resources |
| `fix.py` | (internal) |
| `gitlab.py` | GitLab CI |
| `git_tag.py` | Git Tag |
| `go.py` | Go |
| `gradle_catalog.py` | Gradle Version Catalog |
| `helm.py` | Helm |
| `java.py` | Java/Gradle |
| `jenkins.py` | Jenkins |
| `k8s.py` | Kubernetes |
| `kotlin.py` | Kotlin |
| `kotlin_multiplatform.py` | Kotlin Multiplatform |
| `lineending.py` | Line endings |
| `lockfile.py` | Lockfile |
| `makefile.py` | Makefile |
| `maven.py` | Maven |
| `mise.py` | Mise |
| `nix.py` | Nix |
| `node.py` | Node |
| `npmrc.py` | NPMRC |
| `nvmrc.py` | NVMRC |
| `package_manager.py` | (part of lockfile) |
| `php.py` | PHP |
| `pipfile.py` | Pipfile |
| `pnpm.py` | PNPM workspace |
| `poetry.py` | Poetry |
| `pre_commit.py` | Pre-commit |
| `python.py` | Python |
| `python_version.py` | Python Version Files |
| `renovate.py` | Renovate |
| `requirements.py` | (part of Python) |
| `ruby.py` | Ruby |
| `rust.py` | Rust |
| `rust_workspace.py` | (part of Rust) |
| `swift.py` | Swift |
| `taskfile.py` | Taskfile |
| `terraform.py` | Terraform |
| `tool_versions.py` | Tool versions |
| `typosquat.py` | Typosquat Detection |
| `version_files.py` | Version Files |
| `vscode.py` | VSCode Extensions |
| `yarnrc.py` | Yarn RC |
