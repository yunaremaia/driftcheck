# CI Integration

## GitHub Actions

### Basic (Fail on Drift)

```yaml
- uses: yunaremaia/driftcheck@main
```

This fails the CI job when drift is detected.

### Skip Informational

```yaml
- uses: yunaremaia/driftcheck@main
  with:
    args: "--no-informational"
```

### SARIF (GitHub Code Scanning)

```yaml
- uses: yunaremaia/driftcheck@main
  with:
    sarif: true
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: driftcheck.sarif
```

### Markdown Summary

```yaml
- name: Drift Check
  run: driftcheck --report >> $GITHUB_STEP_SUMMARY
```

## GitLab CI

```yaml
driftcheck:
  image: python:3.11
  script:
    - pip install git+https://github.com/yunaremaia/driftcheck.git
    - driftcheck --no-informational
```

## CircleCI

```yaml
- run:
    name: Drift Check
    command: |
      pip install git+https://github.com/yunaremaia/driftcheck.git
      driftcheck --quiet
```

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/yunaremaia/driftcheck
    rev: v0.1.41
    hooks:
      - id: driftcheck
        args: ["--no-informational"]
```

Install:

```bash
pip install pre-commit
pre-commit install
```

## Local Hook (No pre-commit)

```bash
#!/bin/bash
# .git/hooks/pre-commit
driftcheck --no-informational
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

## Exit Codes

| Code | Meaning | CI Behavior |
|------|---------|-------------|
| 0    | No drift | ✅ Pass |
| 1    | Drift detected | ❌ Fail |
| 2    | Error | ❌ Fail |

## Pro Tips

- Use `--quiet` to suppress OK output in CI logs.
- Use `--no-informational` to skip non-blocking drifts.
- Use `--json > drifts.json` for machine-readable results you can parse in a later step.
- Use `--sarif` to surface drift alerts in the GitHub Security tab.
