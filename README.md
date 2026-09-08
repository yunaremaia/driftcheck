# driftcheck

**Detect version drift between docs and toolchain files.**

`README.md` says Rust 1.93.0 but `rust-toolchain.toml` pins 1.96.1? `CONTRIBUTING.md` says Node 18 but `package.json` engines says 24? `go.mod` says 1.23 but docs say 1.21? `driftcheck` catches it before your contributors hit a build failure.

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
driftcheck           # scan current repo
driftcheck --json    # machine-readable
driftcheck --fix     # auto-fix drifts in documentation files
driftcheck --sarif   # SARIF 2.1.0 output for GitHub Code Scanning
driftcheck --list-detectors  # show available detectors
driftcheck --only tool_versions_drifts  # run specific detectors
driftcheck --exclude nvmrc_drifts,lockfile_drifts  # exclude detectors
driftcheck --quiet   # only output drifts, suppress OK
driftcheck --no-informational  # skip informational drifts
driftcheck --version
```

### GitHub Action

Add driftcheck to your CI with a single step:

```yaml
- uses: yunaremaia/driftcheck@main
  with:
    fail-on-drift: true   # default
    args: "--no-informational"
```

Or with SARIF upload for GitHub Code Scanning:

```yaml
- uses: yunaremaia/driftcheck@main
  with:
    sarif: true
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: driftcheck.sarif
```

### Markdown Report

Generate a markdown summary for CI job summaries or PR comments:

```bash
driftcheck --report          # output markdown to stdout
driftcheck --report >> $GITHUB_STEP_SUMMARY  # post to GitHub Actions
```

### Initialize Config

Generate a starter `.driftcheck.toml`:

```bash
driftcheck --init            # creates .driftcheck.toml with examples
```

### Configuration (`.driftcheck.toml`)

Place a `.driftcheck.toml` file in your repo root to customize detection:

```toml
[driftcheck]
# Exclude specific detectors (supports short names or drift keys)
exclude_detectors = ["lockfile", "nvmrc", "ci_os"]

# Treat informational drifts as blocking
fail_on_informational = false

# Custom doc paths (default: auto-detects README.md, CONTRIBUTING.md, docs/README*.md)
# doc_paths = ["README.md", "docs/guide.md"]
```

You can also use CLI flags `--only` and `--exclude` to filter detectors at runtime.

### Checks (v0.1.35):

**Language runtimes:**
- **Rust**: `rust-toolchain.toml` `channel` **and** `Cargo.toml` `rust-version` vs `README.md` / `docs/README*.md` / `CONTRIBUTING*.md` — minor-aware (patch differences ignored)
- **Node**: `package.json` `engines.node` vs README
- **Bun**: `package.json` `engines.bun` vs README — major.minor comparison
- **Python**: `pyproject.toml` `requires-python` vs README
- **Go**: `go.mod` `go` directive vs README
- **PHP**: `composer.json` `require.php` vs README — major.minor comparison
- **Ruby**: `Gemfile` `ruby "x.y.z"` directive vs README — major.minor comparison
- **.NET/C#**: `*.csproj` `<TargetFramework>` vs README — handles multi-targeting
- **Elixir**: `mix.exs` `elixir:` version vs README
- **Kotlin**: `build.gradle.kts` plugin version vs README
- **Swift**: `Package.swift` `swift-tools-version` and dependency pins vs README
- **Dart/Flutter**: `pubspec.yaml` `environment.sdk` constraint vs README

**Package managers & lockfiles:**
- **Pipfile**: `Pipfile` vs `Pipfile.lock` version mismatches
- **Conda**: `environment.yml` unpinned packages
- **Gradle Version Catalog**: `libs.versions.toml` vs README
- **Lockfile**: missing, stale, or orphaned lockfiles (package-lock.json, yarn.lock, Cargo.lock, go.sum, Gemfile.lock, composer.lock, poetry.lock, uv.lock) (informational)

**CI/CD:**
- **GitHub Actions**: outdated `uses: action@version` — compares against known latest versions for 18 popular actions; detects deprecated Node 20 runtime
- **GitLab CI**: `.gitlab-ci.yml` image tags vs README
- **CircleCI**: `.circleci/config.yml` docker image tags vs README
- **Jenkins**: `Jenkinsfile` tool versions (`nodejs`, `python`, `docker.image`) vs README
- **CI OS**: deprecated GitHub Actions runners (ubuntu-18.04, macos-11, windows-2016)

**Infrastructure:**
- **Docker**: `Dockerfile` `FROM <image>:<tag>` vs README
- **Docker Compose**: `docker-compose.yml`/`compose.yaml` image tags vs README
- **Kubernetes**: image tags in manifests vs README
- **Helm**: `Chart.yaml`/`values.yaml` image tags vs README
- **Terraform**: `versions.tf` `required_providers` block `version` vs README
- **Environment drift**: `.env.example` vs `.env`, `docker-compose.yml` vs `docker-compose.prod.yml`, `values.yaml` vs `values.prod.yaml`

**Build tools:**
- **Makefile**: tool version variables (`GCC_VERSION`, `CMAKE_VERSION`, `GO_VERSION`, etc.)
- **CMake**: `CMakeLists.txt` `cmake_minimum_required` version vs README
- **Maven**: `pom.xml` `java.version`, `maven.compiler.source`, `maven.compiler.target`, `release` vs README
- **Java/Gradle**: `build.gradle` `sourceCompatibility`, `jvmTarget`, `JavaVersion.VERSION_*` vs README

**Configuration:**
- **Tool versions**: `.tool-versions` (asdf/mise) — detects drift for Node, Python, Go, Rust, Ruby, Java, PHP, .NET
- **Version files**: `.ruby-version`, `.python-version`, `.node-version`, `.java-version`, `.terraform-version` vs README
- **NVMRC**: `.nvmrc` vs `package.json` engines.node (informational)
- **Dependabot**: ecosystems used but not covered by `.github/dependabot.yml` (informational)
- **SARIF output**: `driftcheck --sarif` generates SARIF 2.1.0 for GitHub Code Scanning

**Other:**
- **Line endings**: missing `* text=auto eol=lf` in `.gitattributes` (informational)
- **External resources**: third-party CDN dependencies that break offline rendering (informational)
- **Count**: `skills/` directory count vs README mentions of "N skills"
- **Plugins**: custom drift detection via `.driftcheck_plugins/` directory

### Plugins

driftcheck supports plugins for custom drift detection. Create a `.driftcheck_plugins/` directory in your repo root and add Python files that define a `register()` function:

```python
# .driftcheck_plugins/my_detector.py
import re

def register():
    return {"my_detector": find_my_drift}

MY_RE = re.compile(r'my_tool\s+(?P<ver>\d+\.\d+)')

def find_my_drift(root, docs):
    drifts = []
    for fname, content in docs.items():
        for m in MY_RE.finditer(content):
            drifts.append({
                "file": fname,
                "doc_version": m.group("ver"),
                "detail": f"my_tool {m.group('ver')} mentioned",
            })
    return drifts
```

Plugin results appear as `plugin_<name>_drifts` in JSON output and are printed in the CLI. Broken plugins are skipped with a warning — they won't crash driftcheck.

### Pre-commit hook

driftcheck ships a pre-commit hook. Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/yunaremaia/driftcheck
    rev: v0.1.33
    hooks:
      - id: driftcheck
        args: ["--no-informational"]
```

Or use it locally:

```bash
pip install pre-commit
pre-commit install
```

### Stats

- **47 detectors** covering 50+ toolchains and file types
- **388 tests** with >95% code coverage
- **SARIF 2.1.0** output for GitHub Code Scanning
- **Plugin system** for custom detectors
- **Pre-commit hook** support
- **CI matrix**: Python 3.10-3.14, Linux/macOS/Windows

Inspired by fixing https://github.com/tinyhumansai/openhuman/issues/5781 (6 READMEs drifted).
