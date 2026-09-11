# driftcheck

**Detect version drift between docs and toolchain files.**

`README.md` says Rust 1.93.0 but `rust-toolchain.toml` pins 1.96.1? `CONTRIBUTING.md` says Node 18 but `package.json` engines says 24? `go.mod` says 1.23 but docs say 1.21? `driftcheck` catches it before your contributors hit a build failure.

## Quick Start

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
driftcheck           # scan current repo
driftcheck --fix     # auto-fix drifts in documentation files
```

## Features

- **52 detector modules** covering 50+ toolchains
- **60 independent detectors** including CI/CD, infrastructure, and config drift
- **SARIF 2.1.0** output for GitHub Code Scanning
- **Auto-fix** mode (`--fix`) to patch documentation drifts
- **Plugin system** for custom detectors
- **Pre-commit hook** support

## Install

```bash
pip install driftcheck        # from PyPI
# or
pip install git+https://github.com/yunaremaia/driftcheck.git  # from source
```

## License

MIT
