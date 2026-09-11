# Usage

## Scan

Scan a repository for drift:

```bash
driftcheck
```

Scan a specific directory:

```bash
driftcheck /path/to/repo
```

## Auto-Fix

Rewrites documentation files to match toolchain versions:

```bash
driftcheck --fix
```

This modifies the doc files (README.md, CONTRIBUTING.md, etc.) to match the toolchain file values. Lines not mentioning the drifted version are left intact.

## List Detectors

See all 60 available detectors:

```bash
driftcheck --list-detectors
```

## Filter Detectors

Run specific detectors:

```bash
driftcheck --only rust_drifts,node_drifts
```

Exclude specific detectors:

```bash
driftcheck --exclude ci_os_drifts,nvmrc_drifts
```

Short names also work:

```bash
driftcheck --only tool_versions,lockfile_drifts
```

## Informational Drifts

Some detectors (lockfile presence, CI OS, nvmrc mismatch) are informational by default. To treat them as blocking:

```bash
driftcheck --fail-on-informational
```

To skip them entirely:

```bash
driftcheck --no-informational
```

## Quiet Mode

Only output drift findings (suppress "OK" messages):

```bash
driftcheck --quiet
```

## Markdown Report

Generate a markdown summary for CI job summaries or PR comments:

```bash
driftcheck --report >> $GITHUB_STEP_SUMMARY
```

## SARIF Output

Generate SARIF 2.1.0 for GitHub Code Scanning:

```bash
driftcheck --sarif > driftcheck.sarif
```

Then upload with `github/codeql-action/upload-sarif`:

```yaml
- uses: yunaremaia/driftcheck@main
  with:
    sarif: true
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: driftcheck.sarif
```

## Initialize Config

Generate a starter `.driftcheck.toml`:

```bash
driftcheck --init
```

Creates a `.driftcheck.toml` with example configuration options.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | No drift detected |
| 1    | Drift detected (use in CI) |
| 2    | Error (invalid arguments, missing repo, etc.) |

## Exit Codes (Custom)

Make driftcheck always exit 0 (useful for check-only runs):

```bash
driftcheck || true
```
