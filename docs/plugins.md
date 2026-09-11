# Plugins

driftcheck supports custom drift detection via plugins. Create a `.driftcheck_plugins/` directory in your repo root and add Python files that define a `register()` function.

## Plugin Structure

```python
# .driftcheck_plugins/my_detector.py
import re

def register():
    return {"my_detector": find_my_drift}

MY_RE = re.compile(r'my_tool\s+(?P<ver>\d+\.\d+)')

def find_my_drift(root, docs):
    drifts = []
    for fname, content in docs.items():
        for m in MY_RE.finditer(content):
            drifts.append({
                "file": fname,
                "doc_version": m.group("ver"),
                "detail": f"my_tool {m.group('ver')} mentioned",
            })
    return drifts
```

## Plugin API

- `register()` — required. Returns a dict mapping detector names to finder functions.
- `find_my_drift(root, docs)` — `root` is the repo root `Path`, `docs` is a `{filename: content}` dict. Returns a list of drift dicts.
- Plugin results appear as `plugin_<name>_drifts` in JSON output and in CLI output.

## Error Handling

Broken plugins are skipped with a warning. They will not crash driftcheck.

```bash
driftcheck  # warns: Failed to load plugin broken.py: ImportError(...)
```

## Example: Detect Mentions of a Custom Tool

```python
# .driftcheck_plugins/internal_tools.py
import re

INTERNAL_RE = re.compile(r'internal-cli/v(?P<ver>\d+\.\d+)')

def register():
    return {"internal_cli": find_internal_cli}

def find_internal_cli(root, docs):
    drifts = []
    for fname, content in docs.items():
        for m in INTERNAL_RE.finditer(content):
            drifts.append({
                "file": fname,
                "doc_version": m.group("ver"),
                "kind": "internal_cli",
                "detail": f"internal-cli/v{m.group('ver')} referenced",
            })
    return drifts
```

Run:

```bash
driftcheck --only plugin_internal_cli_drifts
```

## Disable Plugins

Plugins are always loaded. To skip a plugin, remove its `.py` file from `.driftcheck_plugins/`.
