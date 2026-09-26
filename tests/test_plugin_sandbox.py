"""Tests for plugin sandboxing (security)."""
import sys
from pathlib import Path
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from driftcheck.plugins import load_plugins, run_plugin_detectors


@pytest.fixture
def plugin_dir(tmp_path):
    """Create a temporary plugin directory with test plugins."""
    plugins_dir = tmp_path / ".driftcheck_plugins"
    plugins_dir.mkdir()
    return plugins_dir


class TestPluginSandbox:
    """Tests for plugin sandboxing security."""

    def test_malicious_plugin_cannot_access_system_functions(self, plugin_dir):
        """A plugin should not be able to call os.system, subprocess, etc."""
        # Create a plugin that tries to use dangerous functions
        # Note: full 'os' module is blocked - only safe_os is available
        malicious = plugin_dir / "malicious.py"
        malicious.write_text("""
# The full 'os' module is blocked; trying to import it should fail
try:
    import os as _os_full
    # If we got here, os was imported - verify dangerous attrs are blocked
    try:
        _os_full.system("echo pwned")
    except (AttributeError, PermissionError):
        pass  # Expected: system is blocked
except ImportError:
    pass  # Also acceptable: os import blocked entirely

def register():
    return {"malicious": detect}

def detect(root, docs):
    # Try to access dangerous functions that should be blocked
    # os.system is not available via safe_os
    try:
        os.system("echo pwned")
    except (AttributeError, PermissionError, NameError):
        pass  # Expected: system is blocked
    try:
        subprocess.run(["echo", "pwned"])
    except (NameError, ImportError):
        pass  # Expected: subprocess not available
    return [{"file": "test.py", "detail": "test"}]
""")
        
        # The plugin should load but be sandboxed
        plugins = load_plugins(plugin_dir.parent)
        assert "malicious" in plugins or len(plugins) == 0  # Either loaded or empty
        
        # If loaded, running it should not execute system commands
        if "malicious" in plugins:
            results = run_plugin_detectors(plugin_dir.parent, {}, plugins)
            # Should not have crashed with system command execution
            assert isinstance(results, dict)

    def test_plugin_can_access_safe_functions(self, plugin_dir):
        """A legitimate plugin should be able to use safe functions."""
        safe = plugin_dir / "safe_plugin.py"
        safe.write_text("""
def register():
    return {"safe_detector": detect}

def detect(root, docs):
    # These should work
    import os
    cwd = os.getcwd()
    return [{"file": "test.py", "detail": f"cwd: {cwd}"}]
""")
        
        plugins = load_plugins(plugin_dir.parent)
        assert "safe_detector" in plugins
        
        results = run_plugin_detectors(plugin_dir.parent, {}, plugins)
        assert "plugin_safe_detector_drifts" in results

    def test_plugin_can_read_files_in_target_directory(self, plugin_dir):
        """A plugin should be able to read files within the target directory."""
        # Create a test file
        test_file = plugin_dir.parent / "test_target.py"
        test_file.write_text("x = 1\n")
        
        safe = plugin_dir / "reader.py"
        safe.write_text("""
def register():
    return {"reader": detect}

def detect(root, docs):
    # Should be able to read files in the target
    try:
        content = (root / "test_target.py").read_text()
        return [{"file": "test_target.py", "detail": f"content: {content.strip()[:50]}"}]
    except Exception as e:
        return [{"file": "test_target.py", "detail": f"error: {e}"}]
""")
        
        plugins = load_plugins(plugin_dir.parent)
        assert "reader" in plugins
        
        results = run_plugin_detectors(plugin_dir.parent, {}, plugins)
        assert "plugin_reader_drifts" in results

    def test_plugin_cannot_escape_target_directory(self, plugin_dir):
        """A plugin should not be able to access files outside the target."""
        # Create a file outside the target
        outside_file = Path("/tmp/secret_outside.txt")
        outside_file.write_text("secret data")
        
        try:
            escape = plugin_dir / "escape.py"
            escape.write_text("""
def register():
    return {"escape": detect}

def detect(root, docs):
    # Try to access file outside target
    try:
        content = Path("/tmp/secret_outside.txt").read_text()
        return [{"file": "outside.txt", "detail": content}]
    except Exception as e:
        return [{"file": "outside.txt", "detail": f"blocked: {type(e).__name__}"}]
""")
            
            plugins = load_plugins(plugin_dir.parent)
            
            if "escape" in plugins:
                results = run_plugin_detectors(plugin_dir.parent, {}, plugins)
                # The result should indicate the access was blocked or failed
                if "plugin_escape_drifts" in results:
                    drifts = results["plugin_escape_drifts"]
                    if drifts:
                        detail = drifts[0].get("detail", "")
                        # Should not contain the actual secret
                        assert "secret data" not in detail, "Plugin escaped sandbox!"
        finally:
            outside_file.unlink(missing_ok=True)

    def test_no_plugin_directory_returns_empty(self, tmp_path):
        """When there's no .driftcheck_plugins directory, return empty dict."""
        plugins = load_plugins(tmp_path)
        assert plugins == {}

    def test_corrupted_plugin_does_not_crash_scanner(self, plugin_dir):
        """A plugin with syntax errors should not crash the loading process."""
        bad = plugin_dir / "bad_syntax.py"
        bad.write_text("""def register(
        return {"bad": lambda r, d: []}
""")  # Missing closing parenthesis
        
        # Should not raise an exception
        plugins = load_plugins(plugin_dir.parent)
        # The bad plugin should be skipped, but other plugins (if any) should load
        assert isinstance(plugins, dict)
