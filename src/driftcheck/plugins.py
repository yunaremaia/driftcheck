"""Plugin system for driftcheck — load custom detectors from .driftcheck_plugins/ directory.

Plugins are Python modules that define a `register()` function returning a dict of
{name: detector_fn}. Each detector_fn takes (root: Path, docs: dict[str, str]) -> list[dict].

Example plugin file (.driftcheck_plugins/my_detector.py):

    def register():
        return {"my_detector": find_my_drift}

    def find_my_drift(root, docs):
        # Your detection logic here
        return [{"file": "README.md", "detail": "example drift"}]
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

# Type alias for a detector function
DetectorFn = Callable[[Path, dict[str, str]], list[dict]]


def load_plugins(root: Path) -> dict[str, DetectorFn]:
    """Load plugins from .driftcheck_plugins/ directory in repo root.

    Returns dict of {detector_name: detector_function}.
    """
    plugins_dir = root / ".driftcheck_plugins"
    if not plugins_dir.is_dir():
        return {}

    plugins: dict[str, DetectorFn] = {}
    for plugin_file in sorted(plugins_dir.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"driftcheck_plugin_{plugin_file.stem}", str(plugin_file)
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                registered = module.register()
                if isinstance(registered, dict):
                    for name, fn in registered.items():
                        if callable(fn):
                            plugins[name] = fn  # type: ignore[assignment]
        except Exception as e:
            # Log but don't crash on plugin errors
            import warnings
            warnings.warn(f"Failed to load plugin {plugin_file.name}: {e}")
    return plugins


def run_plugin_detectors(
    root: Path, docs: dict[str, str], plugins: dict[str, DetectorFn]
) -> dict[str, list[dict]]:
    """Run all loaded plugins and return results keyed by plugin name."""
    results: dict[str, list[dict]] = {}
    for name, fn in plugins.items():
        try:
            result = fn(root, docs)
            if result:
                results[f"plugin_{name}_drifts"] = result
        except Exception as e:
            import warnings
            warnings.warn(f"Plugin {name} failed: {e}")
    return results
