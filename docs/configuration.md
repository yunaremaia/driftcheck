# Configuration

driftcheck is configured via a `.driftcheck.toml` file in the repository root.

## Generate a Config

```bash
driftcheck --init
```

Creates a `.driftcheck.toml` with example configuration.

## Options

```toml
[driftcheck]
# Exclude specific detectors (supports short names or drift keys)
exclude_detectors = ["lockfile", "nvmrc", "ci_os"]

# Treat informational drifts as blocking
fail_on_informational = false

# Custom doc paths — additional files to scan for version mentions
# Supports glob patterns (e.g., "docs/*.md")
doc_paths = ["docs/setup.md", "CHANGELOG.md"]
```

## Detector Exclusion

Exclude specific detectors by short name or full key:

```toml
exclude_detectors = ["rust_drifts", "node", "lockfile"]
```

Short names work too — `"rust"` matches `"rust_drifts"`, `"node"` matches `"node_drifts"`.

## Doc Paths

By default driftcheck scans:
- `README.md`, `README-*.md`, `README_*.md`
- `CONTRIBUTING.md`, `CONTRIBUTING-*.md`
- `docs/README*.md`

Add custom paths:

```toml
doc_paths = [
    "docs/setup.md",
    "docs/getting-started.md",
    "CHANGELOG.md",
    "wiki/*.md",          # glob patterns supported
]
```

## Informational Drifts

Some detectors (lockfile presence, CI OS, nvmrc mismatch) are informational by default. To promote them to blocking:

```toml
fail_on_informational = true
```

Or via CLI:

```bash
driftcheck --fail-on-informational
```

## Runtime Overrides

CLI flags override `.driftcheck.toml`:

```bash
driftcheck --only rust,node           # override exclude_detectors
driftcheck --exclude lockfile,nvmrc   # add to excluded list
driftcheck --fail-on-informational    # promote informational drifts
```

## Full Example

```toml
[driftcheck]
exclude_detectors = ["ci_os_drifts", "nvmrc_drifts", "lockfile_drifts"]
fail_on_informational = false
doc_paths = [
    "docs/setup.md",
    "docs/installation.md",
    "CHANGELOG.md",
]
```
