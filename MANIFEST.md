# Driftcheck Manifest — v0.1.45

## Core Stats
- **62 detector modules** (files in `src/driftcheck/detectors/` excluding `__init__.py`)
- **67 registered detectors** (DRIFT_KEYS in `src/driftcheck/config.py`)
- **64 distinct find_*_drift detectors** exported + 2 internal helpers (`find_env_drift_combined`, `find_rust_drift_multi`)
- **1122 tests** with >95% code coverage
- **SARIF 2.1.0** output for GitHub Code Scanning

## Recent Commits
- `0c94d31` fix: populate empty Dockerfile with working container definition
- `e45e7ce` docs: update MANIFEST.md with current project status
- `e82f6b4` docs: correct detector count to 62 modules (63 files incl __init__)
- `a55b0a9` feat: add Dockerfile instruction drift detector (EXPOSE, HEALTHCHECK, WORKDIR, ENTRYPOINT, USER) (#100)
- `dd4fd70` fix: support single-quoted and Poetry style python version in pyproject.toml
- `cc076a1` docs: add nine missing detectors to README Checks section
- `0ae2b6e` fix: add Python manifests to lockfile missing check (#81)
- `f6e3b50` docs: sync detector counts across all three doc files
- `28033c5` fix: export all 65 find_* functions in __all__ and sync detector counts
- `5771b5e` docs: add MANIFEST.md with full detector inventory and README mapping
- `cdf0883` docs: correct detector module count to 61 (actual files in detectors/)
- `2414515` docs: correct detector counts to 62 modules, 63 registered detectors
- `43d2f86` feat: add Nix flake.lock drift detection
- `f8231a6` docs: correct detector module count to 60 (actual files in detectors/)
- `348fcb0` docs: correct detector counts to match codebase reality (61 modules, 64 registered)
- `9d9d644` docs: update detector counts after Bazel detector merge (60 modules, 64 registered)
- `9caabbf` feat: add Bazel drift detection (#73)
- `b3544a5` docs: correct detector counts to match codebase reality (59 modules, 63 registered)
- `31bca51` docs: add devcontainer and renovate detectors to README Checks section
- `4e81515` docs: correct detector counts to match codebase reality (60 modules, 66 registered, 1089 tests)

## Note on Count
**62 detector module files** in `src/driftcheck/detectors/` (excluding `__init__.py`, which is the package init). **67 registered detectors** in `config.py` (DRIFT_KEYS). All counts verified against the codebase on 2026-09-18.

## Detectors Documented in README "Checks" Section
All 62 detector modules are documented in the README "Checks" section, though some use display names that differ from the file names:

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
| `dotnet.py` | .NET/C# |
| `editorconfig.py` | (Configuration) |
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
| `poetry.py` | (part of Python) |
| `pre_commit.py` | Pre-commit |
| `python.py` | Python |
| `python_version.py` | (part of Python) |
| `renovate.py` | Renovate |
| `requirements.py` | (part of Python) |
| `ruby.py` | Ruby |
| `rust.py` | Rust |
| `swift.py` | Swift |
| `taskfile.py` | (Configuration) |
| `terraform.py` | Terraform |
| `tool_versions.py` | Tool versions |
| `typosquat.py` | (Security) |
| `version_files.py` | Version files |
| `vscode.py` | (Configuration) |
| `yarnrc.py` | Yarn RC |

