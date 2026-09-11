# Getting Started

## Install

```bash
pip install git+https://github.com/yunaremaia/driftcheck.git
```

Verify:

```bash
driftcheck --version
```

## First Scan

Navigate to your repository root and run:

```bash
driftcheck
```

If there is no drift, driftcheck exits 0 with no output (use `--quiet` to suppress the "No drift detected" message).

If drift is found, you'll see output like:

```
rust version drift: rust-toolchain.toml says 1.96.1, README.md says 1.93.0
node version drift: package.json engines.node says 22, README.md says 18
```

driftcheck exits 1 when drift is detected — perfect for CI gates.

## Auto-Fix

```bash
driftcheck --fix
```

Rewrites `README.md` (and other docs) to match the toolchain version. Only touches lines that mention the drifted version; leaves everything else intact.

## Machine-Readable Output

```bash
driftcheck --json
```

Returns a JSON object with typed drift lists:

```json
{
  "rust_drifts": [
    {
      "file": "README.md",
      "doc_version": "1.93.0",
      "toolchain_version": "1.96.1",
      "kind": "rust"
    }
  ],
  "node_drifts": []
}
```

## SARIF (GitHub Code Scanning)

```bash
driftcheck --sarif > driftcheck.sarif
```

Upload the SARIF file with `github/codeql-action/upload-sarif` to see drift alerts in the GitHub Security tab.
