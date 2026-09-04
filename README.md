# driftcheck

**Detect version drift between docs and toolchain files.**

`README.md` says Rust 1.93.0 but `rust-toolchain.toml` pins 1.96.1? `CONTRIBUTING.md` says Node 18 but `package.json` engines says 24? `go.mod` says 1.23 but docs say 1.21? `driftcheck` catches it before your contributors hit a build failure.

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
driftcheck           # scan current repo
driftcheck --json    # machine-readable
driftcheck --fix     # auto-fix drifts in documentation files
```

Checks (v0.1.10):
- Maven: `pom.xml` `java.version`, `maven.compiler.source`, `maven.compiler.target`, `release` vs README mentions — major-version comparison
- Docker: `Dockerfile` `FROM <image>:<tag>` vs `README.md` / `docs/README*.md` / `CONTRIBUTING*.md` — handles variant tags (`24` matches `24-slim`, `24-alpine`), multi-stage builds (`FROM golang:1.23 AS builder` → `FROM alpine:3.21`)
- Java/Gradle: `build.gradle` `sourceCompatibility`, `jvmTarget`, `JavaVersion.VERSION_*` vs README mentions
- Rust: `rust-toolchain.toml` `channel` **and** `Cargo.toml` `rust-version` vs `README.md` / `docs/README*.md` / `CONTRIBUTING*.md`
  - Minor-aware: `channel = "1.96"` matches docs that say `Rust 1.96.1` (patch differences ignored); a real drift is a different major/minor.
- Node: `package.json` `engines.node` vs README
- Python: `pyproject.toml` `requires-python` vs README
- Go: `go.mod` `go` directive vs README
- Line endings: missing `* text=auto eol=lf` in `.gitattributes` (causes CRLF working-tree drift on Windows `core.autocrlf=true`)
- Count: `skills/` directory count vs `README.md` mentions of "N skills" (e.g. 161 vs 163) — catches README/file-count drift like [K-Dense-AI/scientific-agent-skills#240](https://github.com/K-Dense-AI/scientific-agent-skills/issues/240)
- Actions: GitHub Actions pinned to deprecated Node 20 runtime (`actions/checkout@v4`, `setup-node@v4`, `configure-pages@v5`, `deploy-pages@v4`, `pnpm/action-setup@v4`) → suggests `node24` fixed versions (fixes [tt-a1i/archify#217](https://github.com/tt-a1i/archify/issues/217))
- External resources: delivered HTML fetching third-party CDN hosts (`fonts.googleapis.com`, `cdn.jsdelivr`, etc.) — breaks offline/air-gapped rendering (cf. [tt-a1i/archify#242](https://github.com/tt-a1i/archify/issues/242))
- Extensible: add more toolchain sources in `driftcheck/detector.py`

Inspired by fixing https://github.com/tinyhumansai/openhuman/issues/5781 (6 READMEs drifted).
