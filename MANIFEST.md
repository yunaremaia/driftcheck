# Driftcheck Manifest — v0.1.46

## Core Stats
- **66 detector modules** (files in `src/driftcheck/detectors/` excluding `__init__.py`)
- **70 registered detectors** (DRIFT_KEYS in `src/driftcheck/config.py`)
- **70 find_* functions** across detector modules (plus `to_sarif`)
- **1301 tests** with >95% code coverage
- **SARIF 2.1.0** output for GitHub Code Scanning

## Recent Commits
- `73a6829` fix: handle symlink loops in _walk_files
- `070dccc` fix: replace hand-rolled TOML parser with tomllib (fixes #151) (#264)
- `6f6eeeb` fix: wire custom_detectors config into scan_repo (fixes #209) (#245)
- `efd7789` docs: update test count from 1284 to 1308 in MANIFEST.md
- `9271761` fix(test): remove duplicate dict keys flagged by ruff F601
- `b51b195` docs: correct detector module count from 61 to 64
- `7fe043e` feat: make parallel read timeouts configurable (#238) (#242)
- `5742839` docs: correct test count from 1276 to 1284 in MANIFEST.md
- `192c26b` fix: _print_blocking_drifts now handles all drift types (fixes #233) (#237)
- `22dd24f` fix(sarif): URI-encode file paths in artifactLocation.uri (#230)

## Note on Count
**66 detector module files** in `src/driftcheck/detectors/` (excluding `__init__.py`, which is the package init). All counts verified against the codebase on 2026-09-22 (base `c54a342`).

## Detectors Documented in README "Checks" Section
All 66 detector modules are documented in the README "Checks" section, though some use display names that differ from the file names:

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
| `package_version.py` | Package version |
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
