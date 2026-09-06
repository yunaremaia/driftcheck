"""Python drift detection: pyproject.toml requires-python vs README mentions."""
from __future__ import annotations
import re

PY_RE = re.compile(r'Python\s+(?P<ver>[0-9]+\.[0-9]+)', re.I)


def parse_python_version_from_pyproject(text: str) -> str | None:
    # naive parse: requires-python = ">=3.10" or ">=3.10,<3.13"
    m = re.search(r'requires-python\s*=\s*"[^"]*?([0-9]+\.[0-9]+)', text)
    if m:
        return m.group(1)
    # also PEP 621 via [project] requires-python
    return None


def _vtuple(v: str) -> tuple[int, ...]:
    """Version string -> tuple of ints for comparison (e.g. '3.8' -> (3, 8))."""
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return (0,)


def find_python_drift(pyproject_text: str, docs: dict[str, str]) -> list[dict]:
    pv = parse_python_version_from_pyproject(pyproject_text)
    if not pv:
        return []
    pv_t = _vtuple(pv)
    drifts = []
    for fname, content in docs.items():
        for m in PY_RE.finditer(content):
            dv = m.group("ver")
            # Precision filter: skip non-requirement mentions like
            # "CPython 3.11 compatibility stack" or "PyTDC 1.1.15 on CPython 3.11"
            # which are package-specific stacks, not the repo's required Python.
            window_start = max(0, m.start() - 40)
            window_end = min(len(content), m.end() + 40)
            window = content[window_start:window_end].lower()
            if "cpython" in window or "compatibility stack" in window or "pyt" in window and "compatibility" in window:
                # double-check: only skip if CPython is near Python mention
                if "cpython" in content[max(0, m.start()-20):m.start()].lower():
                    continue
                if "compatibility" in window:
                    continue
            # requires-python is a *floor* (minimum supported). A doc that
            # mentions a version >= the floor is fine (e.g. an example using
            # 3.12 while requires-python is >=3.8). Only flag when the doc asks
            # for something BELOW the supported minimum — that means the README
            # is stale and understates what the project requires.
            if _vtuple(dv) < pv_t:
                drifts.append({"file": fname, "doc_version": dv, "pyproject_version": pv, "pos": m.start()})
                break
    return drifts
