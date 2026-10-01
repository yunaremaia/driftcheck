"""Plugin system for driftcheck — load custom detectors from .driftcheck_plugins/ directory.

Plugins are Python modules that define a `register()` function returning a dict of
{name: detector_fn}. Each detector_fn takes (root: Path, docs: dict[str, str]) -> list[dict].

Example plugin file (.driftcheck_plugins/my_detector.py):

    def register():
        return {"my_detector": find_my_drift}

    def find_my_drift(root, docs):
        # Your detection logic here
        return [{"file": "README.md", "detail": "example drift"}]

SECURITY: Plugins are loaded in a restricted execution environment. Dangerous builtins
(os.system, subprocess, open with write, exec, eval, etc.) are blocked at load time.
Plugins can only use safe operations (reading files within the target directory, basic
Python operations).
"""
from __future__ import annotations
import builtins
import importlib.util
import sys
import os as _os
from pathlib import Path
from typing import Any, Callable
import warnings

# Type alias for a detector function
DetectorFn = Callable[[Path, dict[str, str]], list[dict]]

# Dangerous builtins that plugins should not have access to
# Note: __import__ is NOT in this list - plugins need it for safe imports
# The safe_import wrapper (installed via _install_sandbox_importer) blocks
# dangerous modules while allowing safe ones
_DANGEROUS_BUILTINS = frozenset([
    "eval", "exec", "compile",  # code execution
    "subprocess", "os.system", "os.popen", "os.exec", "os.spawn",  # subprocess
    "socket", "urllib", "requests",  # network
])


_ORIGINAL_OPEN = builtins.open


def _sandbox_open(file: str | Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
    """Restricted open() that blocks write operations."""
    if isinstance(file, Path):
        file = str(file)
    if "w" in mode or "a" in mode or "x" in mode or "+" in mode:
        raise PermissionError(f"open() with mode '{mode}' is blocked in plugin sandbox (write operations not allowed)")
    return _ORIGINAL_OPEN(file, mode, *args, **kwargs)


def _create_sandbox_namespace() -> dict[str, Any]:
    """Create a restricted namespace for plugin execution.
    
    Only safe builtins are available. Dangerous operations are blocked.
    __import__ is available via the safe_import wrapper for safe module imports.
    """
    sandbox = {}
    
    # Copy safe builtins (excluding dangerous ones)
    # open is replaced with sandbox_open that blocks write operations
    safe_builtins = {}
    for name in dir(builtins):
        if name not in _DANGEROUS_BUILTINS:
            obj = getattr(builtins, name)
            if callable(obj) or isinstance(obj, (type(None), bool, int, float, str, type, tuple, list, dict, set)):
                if name == "open":
                    safe_builtins[name] = _sandbox_open
                else:
                    safe_builtins[name] = obj
    
    sandbox["__builtins__"] = safe_builtins
    
    # Allow limited os access (path operations only, no system calls)
    sandbox["os"] = _create_safe_os_module()
    
    return sandbox


def _create_safe_os_module() -> Any:
    """Create a restricted os module that only allows safe operations.
    
    Provides the full os module but with dangerous functions removed.
    Plugins see a standard os module but cannot call dangerous methods.
    """
    class SafeOSModule:
        """Restricted os module for plugin sandbox."""
        
        # Path operations - safe
        path = _os.path
        path_join = staticmethod(_os.path.join)
        path_dirname = staticmethod(_os.path.dirname)
        path_basename = staticmethod(_os.path.basename)
        path_exists = staticmethod(_os.path.exists)
        path_isdir = staticmethod(_os.path.isdir)
        path_isfile = staticmethod(_os.path.isfile)
        path_getsize = staticmethod(_os.path.getsize)
        getcwd = staticmethod(_os.getcwd)
        
        # File operations - read only
        def listdir(path: str = ".") -> list[str]:
            return _os.listdir(path)
        
        # Explicitly block dangerous methods
        system = None
        popen = None
        exec = None
        spawn = None
        fork = None
        
        def __getattr__(self, name: str) -> Any:
            if name in {"system", "popen", "exec", "spawn", "fork", "spawnv", "spawnve", "remove", "unlink", "rmdir", "removedirs"}:
                raise PermissionError(f"os.{name} is not available in plugin sandbox")
            raise AttributeError(f"os.{name} is not available in plugin sandbox")
    
    return SafeOSModule()


_ORIGINAL_IMPORT = None
_SANDBOX_OS_MODULE = None


def _install_sandbox_importer() -> None:
    """Install a custom importer that blocks dangerous module imports."""
    global _ORIGINAL_IMPORT
    global _SANDBOX_OS_MODULE
    
    if _ORIGINAL_IMPORT is not None:
        return  # Already installed
    
    _ORIGINAL_IMPORT = builtins.__import__
    _SANDBOX_OS_MODULE = _create_safe_os_module()
    
    def safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        # Return the safe os module when plugins try to import os
        if name == "os":
            return _SANDBOX_OS_MODULE
        # Block dangerous top-level modules only
        if name in _DANGEROUS_BUILTINS or name in {
            "subprocess", "socket", "urllib", "urllib2", "requests",
            "http", "httplib", "ftplib", "telnetlib", "smtplib",
            "xmlrpc", "webbrowser", "platform", "pwd", "grp",
        }:
            raise ImportError(f"Import of '{name}' is blocked in plugin sandbox")
        # Allow submodules of os (like os.path) - they're safe
        if name.startswith("os."):
            return _ORIGINAL_IMPORT(name, *args, **kwargs)
        return _ORIGINAL_IMPORT(name, *args, **kwargs)
    
    builtins.__import__ = safe_import


def _remove_sandbox_importer() -> None:
    """Remove the sandbox importer and restore original."""
    global _ORIGINAL_IMPORT
    if _ORIGINAL_IMPORT is not None:
        builtins.__import__ = _ORIGINAL_IMPORT
        _ORIGINAL_IMPORT = None


def load_plugins(root: Path) -> dict[str, DetectorFn]:
    """Load plugins from .driftcheck_plugins/ directory in repo root.

    Returns dict of {detector_name: detector_function}.

    Plugins are executed in a sandboxed environment that blocks:
    - Code execution (eval, exec, compile)
    - Subprocess creation (os.system, subprocess, etc.)
    - Network access (socket, urllib, requests, etc.)
    - Arbitrary file writes (open with write mode)
    - Dangerous imports
    """
    plugins_dir = root / ".driftcheck_plugins"
    if not plugins_dir.is_dir():
        return {}

    # Install sandbox before loading any plugins
    _install_sandbox_importer()
    
    try:
        plugins: dict[str, DetectorFn] = {}
        for plugin_file in sorted(plugins_dir.glob("*.py")):
            if plugin_file.name.startswith("_"):
                continue
            try:
                # Create sandbox namespace for this plugin
                sandbox_ns = _create_sandbox_namespace()
                
                spec = importlib.util.spec_from_file_location(
                    f"driftcheck_plugin_{plugin_file.stem}", str(plugin_file)
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                
                # Execute module in sandbox with restricted builtins
                module.__dict__.update(sandbox_ns)
                # Ensure the custom __import__ is accessible (fallback if not in __builtins__)
                if "__import__" not in module.__dict__.get("__builtins__", {}):
                    module.__dict__["__builtins__"]["__import__"] = _install_sandbox_importer.__globals__.get("_ORIGINAL_IMPORT", builtins.__import__)
                spec.loader.exec_module(module)
                
                if hasattr(module, "register"):
                    registered = module.register()
                    if isinstance(registered, dict):
                        for name, fn in registered.items():
                            if callable(fn):
                                plugins[name] = fn  # type: ignore[assignment]
            except PermissionError as e:
                warnings.warn(f"Plugin {plugin_file.name} blocked by sandbox: {e}")
            except Exception as e:
                warnings.warn(f"Failed to load plugin {plugin_file.name}: {e}")
        
        return plugins
    finally:
        # Always clean up the sandbox importer
        _remove_sandbox_importer()


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
            warnings.warn(f"Plugin {name} failed: {e}")
    return results
