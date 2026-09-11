# Detectors

driftcheck ships **52 detector modules** covering **60 independent detectors**. Each checks for a specific kind of version drift between toolchain files and documentation.

## Language Runtimes

| Detector | Description |
|----------|-------------|
| `rust_drifts` | `rust-toolchain.toml` `channel` and `Cargo.toml` `rust-version` vs README. Minor-aware (patch differences ignored). |
| `node_drifts` | `package.json` `engines.node` vs README. |
| `bun_drifts` | `package.json` `engines.bun` vs README. Major.minor comparison. |
| `python_drifts` | `pyproject.toml` `requires-python` vs README. |
| `go_drifts` | `go.mod` `go` directive vs README. |
| `php_drifts` | `composer.json` `require.php` vs README. Major.minor comparison. |
| `ruby_drifts` | `Gemfile` `ruby "x.y.z"` vs README. Major.minor comparison. |
| `dotnet_drifts` | `*.csproj` `<TargetFramework>` vs README. Handles multi-targeting. |
| `elixir_drifts` | `mix.exs` `elixir:` version vs README. |
| `kotlin_drifts` | `build.gradle.kts` plugin version vs README. |
| `swift_drifts` | `Package.swift` `swift-tools-version` and dependency pins vs README. |
| `dart_drifts` | `pubspec.yaml` `environment.sdk` constraint vs README. |

## Package Managers & Lockfiles

| Detector | Description |
|----------|-------------|
| `pipfile_drifts` | `Pipfile` vs `Pipfile.lock` version mismatches. |
| `conda_drifts` | `environment.yml` unpinned packages. |
| `gradle_catalog_drifts` | `libs.versions.toml` (Gradle version catalog) vs README. |
| `lockfile_drifts` | Missing, stale, or orphaned lockfiles (informational). |
| `npmrc_drifts` | `.npmrc` registry vs README mentions. |
| `yarnrc_drifts` | `.yarnrc.yml` Yarn version vs README mentions. |
| `pnpm_workspace_drifts` | `pnpm-workspace.yaml` packages vs `package.json` workspaces. |

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
| `docker_drifts` | `Dockerfile` `FROM <image>:<tag>` vs README. |
| `dc_drifts` | `docker-compose.yml`/`compose.yaml` image tags vs README. |
| `k8s_drifts` | Kubernetes manifest image tags vs README. |
| `helm_drifts` | `Chart.yaml`/`values.yaml` image tags vs README. |
| `terraform_drifts` | `versions.tf` `required_providers` `version` vs README. |
| `env_drifts` | `.env.example` vs `.env`, `docker-compose.yml` vs `docker-compose.prod.yml`. |

## Build Tools

| Detector | Description |
|----------|-------------|
| `makefile_drifts` | Makefile tool version variables (`GCC_VERSION`, `CMAKE_VERSION`, `GO_VERSION`). |
| `cmake_drifts` | `CMakeLists.txt` `cmake_minimum_required` version vs README. |
| `maven_drifts` | `pom.xml` `java.version`, `maven.compiler.source/target` vs README. |
| `java_gradle_drifts` | `build.gradle` `sourceCompatibility`, `jvmTarget` vs README. |
| `taskfile_drifts` | `Taskfile.yml` tool version variables vs README. |

## Configuration

| Detector | Description |
|----------|-------------|
| `tool_versions_drifts` | `.tool-versions` (asdf/mise) — Node, Python, Go, Rust, Ruby, Java, PHP, .NET. |
| `mise_drifts` | `mise.toml` `[tools]` section vs README. |
| `version_files_drifts` | `.ruby-version`, `.python-version`, `.node-version`, etc. vs README. |
| `nvmrc_drifts` | `.nvmrc` vs `package.json` engines.node (informational). |
| `dependabot_drifts` | Ecosystems used but not covered by `.github/dependabot.yml` (informational). |
| `git_tag_drifts` | Latest git tag vs README version mentions. |

## Other

| Detector | Description |
|----------|-------------|
| `lineending_drifts` | Missing `* text=auto eol=lf` in `.gitattributes` (informational). |
| `external_resource_drifts` | Third-party CDN dependencies that break offline rendering (informational). |
| `count_drifts` | `skills/` directory count vs README mentions of "N skills". |
| `plugin_<name>_drifts` | Custom drift detection via plugins. |

## Detector Aliases

Many detectors can be referenced by short name in `--only`/`--exclude`:

```bash
driftcheck --only rust,node,python,go
driftcheck --exclude lockfile,nvmrc,ci_os
```

The short name is the detector's `kind` prefix (before `_drifts`).
