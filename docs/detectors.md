# Detectors

driftcheck ships **61 detector modules** covering **68 registered detectors**. Each checks for a specific kind of version drift between toolchain files and documentation.

## Language Runtimes

| Detector | Description |
|----------|-------------|
| `bun_drifts` | `package.json` `engines.bun` vs README. Major.minor comparison. |
| `dart_drifts` | `pubspec.yaml` `environment.sdk` constraint vs README. |
| `deno_drifts` | `deno.json` version pins vs README. |
| `dotnet_drifts` | `*.csproj` `<TargetFramework>` vs README. Handles multi-targeting. |
| `elixir_drifts` | `mix.exs` `elixir:` version vs README. |
| `go_drifts` | `go.mod` `go` directive vs README. |
| `java_drifts` | `pom.xml` Maven compiler source/target version vs README. |
| `kotlin_drifts` | `build.gradle.kts` plugin version vs README. |
| `node_drifts` | `package.json` `engines.node` vs README. |
| `php_drifts` | `composer.json` `require.php` vs README. Major.minor comparison. |
| `python_drifts` | `pyproject.toml` `requires-python` vs README. |
| `python_version_drifts` | `.python-version` vs `pyproject.toml` `requires-python` floor. |
| `ruby_drifts` | `Gemfile` `ruby "x.y.z"` vs README. Major.minor comparison. |
| `rust_drifts` | `rust-toolchain.toml` `channel` and `Cargo.toml` `rust-version` vs README. Minor-aware (patch differences ignored). |
| `swift_drifts` | `Package.swift` `swift-tools-version` and dependency pins vs README. |

## Package Managers & Lockfiles

| Detector | Description |
|----------|-------------|
| `conda_drifts` | `environment.yml` unpinned packages. |
| `gradle_catalog_drifts` | `libs.versions.toml` (Gradle version catalog) vs README. |
| `lockfile_drifts` | Missing, stale, or orphaned lockfiles (informational). |
| `npmrc_drifts` | `.npmrc` registry vs README mentions. |
| `package_manager_drifts` | `packageManager` field vs detected lockfile (npm/pnpm/yarn/bun). |
| `pnpm_drifts` | `pnpm-lock.yaml` version drift vs README. |
| `pipfile_drifts` | `Pipfile` vs `Pipfile.lock` version mismatches. |
| `poetry_drifts` | `pyproject.toml` `[tool.poetry]` dependency versions vs README. |
| `python_version_drifts` | `.python-version` vs `pyproject.toml` `requires-python` floor. |
| `requirements_drifts` | `requirements.txt` unpinned packages vs known latest. |
| `yarnrc_drifts` | `.yarnrc.yml` Yarn version vs README mentions. |

## CI/CD

| Detector | Description |
|----------|-------------|
| `actions_drifts` | Outdated `uses: action@version` for 18 popular actions. Detects deprecated Node 20 runtime. |
| `gh_actions_version_drifts` | Outdated GitHub Actions versions by category. |
| `gitlab_drifts` | `.gitlab-ci.yml` image tags vs README. |
| `circleci_drifts` | `.circleci/config.yml` docker image tags vs README. |
| `jenkins_drifts` | `Jenkinsfile` tool versions (`nodejs`, `python`, `docker.image`) vs README. |
| `ci_os_drifts` | Deprecated GitHub Actions runners (ubuntu-18.04, macos-11, windows-2016). |

## Infrastructure

| Detector | Description |
|----------|-------------|
| `compose_drifts` | Docker Compose service image/tag drift vs README. |
| `dc_drifts` | `docker-compose.yml`/`compose.yaml` image tags vs README. |
| `devcontainer_drifts` | Devcontainer.json features/base image vs README. |
| `docker_bases_drifts` | Dockerfile `FROM` base image drift across multi-stage builds. |
| `docker_drifts` | `Dockerfile` `FROM <image>:<tag>` vs README. |
| `docker_multistage_drifts` | Multi-stage Dockerfile FROM consistency across stages. |
| `env_drift_drifts` | `.env.example` vs `.env`, `docker-compose.yml` vs `docker-compose.prod.yml`. |
| `external_drifts` | Third-party CDN dependencies that break offline rendering (informational). |
| `k8s_drifts` | Kubernetes manifest image tags vs README. |

## Build Tools

| Detector | Description |
|----------|-------------|
| `cmake_drifts` | `CMakeLists.txt` `cmake_minimum_required` version vs README. |
| `java_gradle_drifts` | `build.gradle` `sourceCompatibility`, `jvmTarget` vs README. |
| `makefile_drifts` | Makefile tool version variables (`GCC_VERSION`, `CMAKE_VERSION`, `GO_VERSION`). |
| `maven_drifts` | `pom.xml` `java.version`, `maven.compiler.source/target` vs README. |
| `taskfile_drifts` | `Taskfile.yml` tool version variables vs README. |
| `terraform_drifts` | `versions.tf` `required_providers` `version` vs README. |

## Configuration

| Detector | Description |
|----------|-------------|
| `dependabot_drifts` | Ecosystems used but not covered by `.github/dependabot.yml` (informational). |
| `editorconfig_drifts` | `.editorconfig` indent_size/indent_style consistency vs project convention. |
| `engines_drifts` | `package.json` `engines` field consistency across package managers. |
| `git_tag_drifts` | Latest git tag vs README version mentions. |
| `mise_drifts` | `mise.toml` `[tools]` section vs README. |
| `nvmrc_drifts` | `.nvmrc` vs `package.json` engines.node (informational). |
|| `pre_commit_drifts` | Pre-commit hook versions vs `.pre-commit-config.yaml`. |
|| `changelog_drifts` | CHANGELOG.md presence/content vs CONTRIBUTING.md policy (informational). |
|| `tool_versions_drifts` | `.tool-versions` (asdf/mise) — Node, Python, Go, Rust, Ruby, Java, PHP, .NET. |
| `version_files_drifts` | `.ruby-version`, `.python-version`, `.node-version`, etc. vs README. |

## Other

| Detector | Description |
|----------|-------------|
| `count_drifts` | `skills/` directory count vs README mentions of "N skills". |
| `env_drift_drifts` | `.env.example` vs `.env`, `docker-compose.yml` vs `docker-compose.prod.yml`. |
| `external_drifts` | Third-party CDN dependencies that break offline rendering (informational). |
| `fix_drifts` | Auto-correct detected drifts in documentation files (fix application module). |
| `helm_drifts` | `Chart.yaml`/`values.yaml` image tags vs README. |
| `lineending_drifts` | Missing `* text=auto eol=lf` in `.gitattributes` (informational). |
| `package_manager_drifts` | `packageManager` field vs detected lockfile (npm/pnpm/yarn/bun). |
| `plugin_<name>_drifts` | Custom drift detection via plugins. |
| `pnpm_drifts` | `pnpm-lock.yaml` version drift vs README. |
| `poetry_drifts` | `pyproject.toml` `[tool.poetry]` dependency versions vs README. |
| `python_version_drifts` | `.python-version` vs `pyproject.toml` `requires-python` floor. |
| `requirements_drifts` | `requirements.txt` unpinned packages vs known latest. |
| `renovate_drifts` | `renovate.json` configuration health checks (packageRules, managerPolicy). |
| `typosquat_drifts` | Suspicious package names similar to popular packages (security). |
| `vscode_drifts` | `extensions.json` recommendations vs README mentions. |

## Detector Aliases

Many detectors can be referenced by short name in `--only`/`--exclude`:

```bash
driftcheck --only rust,node,python,go
driftcheck --exclude lockfile,nvmrc,ci_os
```

The short name is the detector's `kind` prefix (before `_drifts`).
