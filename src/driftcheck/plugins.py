"""Plugin system for driftcheck — load custom detectors from .driftcheck_plugins/ directory
and from custom_detectors paths in .driftcheck.toml config.

Plugins are Python modules that define a `register()` function returning a dict of
{name: detector_fn}. Each detector_fn takes (root: Path, docs: dict[str, str]) -> list[dict].

Example plugin file (.driftcheck_plugins/my_detector.py):

    def register():
        return {"my_detector": find_my_drift}

    def find_my_drift(root, docs):
        # Your detection logic here
        return [{"file": "README.md", "detail": "example drift"}]

Custom detectors from config (.driftcheck.toml):

    [driftcheck]
    custom_detectors = ["path/to/detector.py", "another/detector.py"]
"""
from __future__ import annotations
import importlib.util
import sys
import threading
from pathlib import Path

_plugin_lock = threading.Lock()
from typing import Any, Callable

# Type alias for a detector function
DetectorFn = Callable[[Path, dict[str, str]], list[dict]]


def _load_plugin_file(plugin_file: Path) -> dict[str, DetectorFn]:
    """Load a single plugin file and return its registered detectors.

    Returns empty dict on any error (logs warning).
    """
    import warnings
    try:
        spec = importlib.util.spec_from_file_location(
            f"driftcheck_plugin_{plugin_file.stem}", str(plugin_file)
        )
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if hasattr(module, "register"):
            registered = module.register()
            if isinstance(registered, dict):
                result = {}
                for name, fn in registered.items():
                    if callable(fn):
                        result[name] = fn  # type: ignore[assignment]
                return result
    except Exception as e:
        warnings.warn(f"Failed to load plugin {plugin_file.name}: {e}")
    return {}


def load_plugins(root: Path, extra_paths: list[str] | None = None) -> dict[str, DetectorFn]:
    """Load plugins from .driftcheck_plugins/ directory and extra paths.

    Thread-safe: plugins are loaded once per process, protected by a lock.

    Args:
        root: repo root path (for .driftcheck_plugins/ directory)
        extra_paths: additional file paths to load as plugins (from custom_detectors config)

    Returns dict of {detector_name: detector_function}.
    """
    with _plugin_lock:
        plugins: dict[str, DetectorFn] = {}

        # Load from .driftcheck_plugins/ directory
        plugins_dir = root / ".driftcheck_plugins"
        if plugins_dir.is_dir():
            for plugin_file in sorted(plugins_dir.glob("*.py")):
                if plugin_file.name.startswith("_"):
                    continue
                result = _load_plugin_file(plugin_file)
                plugins.update(result)

        # Load from custom_detectors paths in config (issue #209)
        if extra_paths:
            for path_str in extra_paths:
                plugin_file = Path(path_str)
                if not plugin_file.is_absolute():
                    plugin_file = root / plugin_file
                if plugin_file.is_file() and plugin_file.suffix == ".py":
                    if not plugin_file.name.startswith("_"):
                        result = _load_plugin_file(plugin_file)
                        plugins.update(result)

        return plugins


def run_plugin_detectors(
    root: Path, docs: dict[str, str], plugins: dict[str, DetectorFn]
) -> dict[str, list[dict]]:
    """Run all loaded plugins and return results keyed by plugin name."""
    results: dict[str, list[dict]] = {}
    import warnings
    for name, fn in plugins.items():
        try:
            result = fn(root, docs)
            if result:
                results[f"plugin_{name}_drifts"] = result
        except Exception as e:
            warnings.warn(f"Plugin {name} failed: {e}")
    return results
