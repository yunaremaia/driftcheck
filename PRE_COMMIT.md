# Pre-commit hook for driftcheck

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/yunaremaia/driftcheck
    rev: main
    hooks:
      - id: driftcheck
        args: ["--no-informational"]
```

Or use it locally:

```bash
# Install pre-commit
pip install pre-commit

# Add to .pre-commit-config.yaml
repos:
  - repo: https://github.com/yunaremaia/driftcheck
    rev: main
    hooks:
      - id: driftcheck

# Install hooks
pre-commit install

# Run manually
pre-commit run driftcheck --all-files
```
