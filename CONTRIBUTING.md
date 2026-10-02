# Contributing to driftcheck

Thank you for your interest in contributing! This document will help you get started.

## Development Setup

**Requirements:**
- Python 3.10+
- pip or uv

**Setup:**

```bash
git clone https://github.com/yunaremaia/driftcheck.git
cd driftcheck
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .
pip install pytest pytest-cov
```

## Running Tests

```bash
pytest -q                          # run all tests (coverage on, gate enforced)
pytest -q --no-cov tests/test_csv_output.py    # run a subset, skip the gate
```

Coverage is enabled by default through `addopts` in `pyproject.toml`, and the
floor is `fail_under` in `[tool.coverage.report]`. A full `pytest -q` therefore
fails if the total drops below the floor. When you run a subset the total is
naturally far below it, so pass `--no-cov` for targeted runs.

When you add tests, keep the floor honest: it is a floor, not a ratchet. Raise it
in the same PR that pushes the total up.

We aim for 90%+ coverage on new code.

**Testing / CI Tip:**
When testing CLI behavior locally or verifying strict rules, use `--fail-on-informational` to treat informational drifts (such as missing lockfiles) as exit code 1 failures.

## Project Structure

```
driftcheck/
├── src/driftcheck/
│   ├── cli.py          # CLI interface, argument parsing
│   ├── detector.py     # scan_repo() and apply_fixes()
│   ├── detectors/      # Individual detector modules
│   ├── sarif.py        # SARIF 2.1.0 output
│   ├── config.py       # DRIFT_KEYS and config loading
│   ├── git_mode.py     # Git-mode scanning (--git-mode)
│   └── plugins.py      # Plugin system
├── tests/              # Test suite
├── .github/workflows/  # CI/CD
└── pyproject.toml      # Build config
```

## Code Style

- Formatter: `ruff format`
- Linter: `ruff check`
- Type hints: encouraged on all functions
- Docstrings: Google style

## Adding a New Detector

1. Create `src/driftcheck/detectors/your_detector.py`
2. Implement `find_your_drift(root: Path, docs: str) -> list[dict]`
3. Import in `src/driftcheck/detectors/__init__.py`
4. Add to `DETECTOR_INFO` dict in `cli.py`
5. Add to `scan_repo()` in `detector.py`
6. Add tests in `tests/`

Example detector skeleton:

```python
"""Detect YourTool version drift."""
import re
from pathlib import Path

def find_your_drift(root: Path, docs: str) -> list[dict]:
    """Detect drift between README and yourtool.toml."""
    results = []
    config_path = root / "yourtool.toml"
    if not config_path.exists():
        return results
    
    config_version = _parse_version(config_path.read_text())
    pattern = rf"yourtool\s+([0-9]+\.[0-9]+\.[0-9]+)"
    
    for match in re.finditer(pattern, docs, re.IGNORECASE):
        doc_version = match.group(1)
        if doc_version != config_version:
            results.append({
                "file": "README.md",
                "tool": "yourtool",
                "doc_version": doc_version,
                "config_version": config_version,
                "pos": match.start(),
            })
    return results
```

## Commit Message Convention

We follow Conventional Commits:

- `feat: add Gradle Version Catalog detector`
- `fix: handle empty Pipfile.lock gracefully`
- `docs: update README with CSV examples`
- `test: add coverage for npmrc edge cases`

## Release Process

Releases are automated via GitHub Actions:

1. Version is bumped in `pyproject.toml` and `__init__.py`
2. A tag `v0.1.X` is created and pushed
3. `publish.yml` attempts to publish to PyPI via trusted publishing

Step 3 currently fails with `invalid-publisher`: no trusted publisher is
registered for this project on pypi.org, so `driftcheck` has never been
published. The workflow itself is wired correctly, and
`tests/test_publish_workflow_config.py` guards that wiring — the missing piece
is the pypi.org publisher registration, which needs account access. Install
from git in the meantime: `pip install git+https://github.com/yunaremaia/driftcheck.git`.

## PR Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes, add tests
4. Run tests: `pytest -q`
5. Commit, push, and open a PR
6. CI will run automatically

For bug fixes, include the issue number: `Closes #123`

## Reporting Issues

Use GitHub Issues with one of these labels:
- `bug` — something is broken
- `enhancement` — new feature request
- `good first issue` — beginner-friendly task

## Code of Conduct

Be respectful, constructive, and professional. Disagreement is fine; hostility is not.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
