# driftcheck

**Detect version drift between docs and toolchain files.**

`README.md` says Rust 1.93.0 but `rust-toolchain.toml` pins 1.96.1? `CONTRIBUTING.md` says Node 18 but `package.json` engines says 24? `driftcheck` catches it before your contributors hit a build failure.

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
driftcheck           # scan current repo
driftcheck --json    # machine-readable
```

Checks (v0.1):
- Rust: `rust-toolchain.toml` `channel` vs `README.md` / `docs/README*.md` / `CONTRIBUTING*.md`
- Node: `package.json` `engines.node` vs README
- Extensible: add more toolchain sources in `driftcheck/detector.py`

Inspired by fixing https://github.com/tinyhumansai/openhuman/issues/5781 (6 READMEs drifted).
