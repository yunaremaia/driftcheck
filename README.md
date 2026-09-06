# driftcheck

**Detect version drift between docs and toolchain files.**

`README.md` says Rust 1.93.0 but `rust-toolchain.toml` pins 1.96.1? `CONTRIBUTING.md` says Node 18 but `package.json` engines says 24? `go.mod` says 1.23 but docs say 1.21? `driftcheck` catches it before your contributors hit a build failure.

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
driftcheck           # scan current repo
driftcheck --json    # machine-readable
driftcheck --fix     # auto-fix drifts in documentation files
```

Checks (v0.1.23):
- Kubernetes: image tags in manifests (`k8s/**/*.yaml`, `deploy/**/*.yaml`) vs README mentions — handles variant tags
- Helm: `Chart.yaml`/`values.yaml` image tags vs README mentions — handles variant tags (`tag:` and `version:` keys)
- Docker Compose: `docker-compose.yml`/`compose.yaml` image tags vs README mentions — handles variant tags
- Dependabot: ecosystems used by the repo but not covered by `.github/dependabot.yml` (informational, non-blocking)
- GitHub Actions version: detect outdated `uses: action@version` in `.github/workflows/*.yml/.yaml` — compares against known latest versions for 18 popular actions
- GitLab CI: `.gitlab-ci.yml` image tags vs README mentions
- CircleCI: `.circleci/config.yml` docker image tags vs README mentions
- Terraform: `versions.tf` `required_providers` block `version` vs README mentions
- Maven: `pom.xml` `java.version`, `maven.compiler.source`, `maven.compiler.target`, `release` vs README mentions
- Docker: `Dockerfile` `FROM <image>:<tag>` vs README mentions
- Java/Gradle: `build.gradle` `sourceCompatibility`, `jvmTarget`, `JavaVersion.VERSION_*` vs README mentions
- Rust: `rust-toolchain.toml` `channel` **and** `Cargo.toml` `rust-version` vs `README.md` / `docs/README*.md` / `CONTRIBUTING*.md`
  - Minor-aware: `channel = "1.96"` matches docs that say `Rust 1.96.1` (patch differences ignored); a real drift is a different major/minor.
- Node: `package.json` `engines.node` vs README
- Bun: `package.json` `engines.bun` vs README — major.minor comparison
- Python: `pyproject.toml` `requires-python` vs README
- Go: `go.mod` `go` directive vs README
- PHP: `composer.json` `require.php` vs README — major.minor comparison (patch differences ignored)
- Line endings: missing `* text=auto eol=lf` in `.gitattributes` (causes CRLF working-tree drift on Windows `core.autocrlf=true`) — only fires when repo has source files
- Count: `skills/` directory count vs `README.md` mentions of "N skills" (e.g. 161 vs 163) — catches README/file-count drift like [K-Dense-AI/scientific-agent-skills#240](https://github.com/K-Dense-AI/scientific-agent-skills/issues/240)
- Actions: GitHub Actions pinned to deprecated Node 20 runtime (`actions/checkout@v4`, `setup-node@v4`, `configure-pages@v5`, `deploy-pages@v4`, `pnpm/action-setup@v4`) → suggests `node24` fixed versions (fixes [tt-a1i/archify#217](https://github.com/tt-a1i/archify/issues/217))
- .NET/C#: `*.csproj` `<TargetFramework>` vs README mentions — handles multi-targeting (first TFM wins); matches ".NET X.Y" in docs
- External resources: delivered HTML fetching third-party CDN hosts (`fonts.googleapis.com`, `cdn.jsdelivr`, etc.) — breaks offline/air-gapped rendering (cf. [tt-a1i/archify#242](https://github.com/tt-a1i/archify/issues/242)) (informational, non-blocking)
- Ruby: `Gemfile` `ruby "x.y.z"` directive vs README mentions — major.minor comparison (patch differences ignored); skips TOC numbered-list lines

Inspired by fixing https://github.com/tinyhumansai/openhuman/issues/5781 (6 READMEs drifted).
