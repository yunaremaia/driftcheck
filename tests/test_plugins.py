"""Tests for the plugin system."""
import textwrap
from pathlib import Path
import tempfile

from driftcheck.plugins import load_plugins, run_plugin_detectors


def _make_plugin(root, name, code):
    """Create a plugin file in the .driftcheck_plugins/ directory."""
    plugins_dir = root / ".driftcheck_plugins"
    plugins_dir.mkdir(exist_ok=True)
    (plugins_dir / f"{name}.py").write_text(textwrap.dedent(code))


class TestLoadPlugins:
    def test_no_plugins_dir(self, tmp_path):
        assert load_plugins(tmp_path) == {}

    def test_empty_plugins_dir(self, tmp_path):
        (tmp_path / ".driftcheck_plugins").mkdir()
        assert load_plugins(tmp_path) == {}

    def test_load_simple_plugin(self, tmp_path):
        _make_plugin(tmp_path, "simple", """
            def register():
                return {"simple": find_simple}

            def find_simple(root, docs):
                return [{"file": "README.md", "detail": "simple drift"}]
        """)
        plugins = load_plugins(tmp_path)
        assert "simple" in plugins
        assert callable(plugins["simple"])

    def test_plugin_with_import_error_ignored(self, tmp_path):
        _make_plugin(tmp_path, "broken", """
            import nonexistent_module_xyz

            def register():
                return {"broken": find_broken}
        """)
        # Should not crash, just skip the broken plugin
        plugins = load_plugins(tmp_path)
        assert "broken" not in plugins

    def test_underscore_files_ignored(self, tmp_path):
        _make_plugin(tmp_path, "_private", """
            def register():
                return {"private": find_private}
        """)
        plugins = load_plugins(tmp_path)
        assert "private" not in plugins

    def test_plugin_without_register_ignored(self, tmp_path):
        _make_plugin(tmp_path, "no_register", """
            def find_no_register(root, docs):
                return []
        """)
        plugins = load_plugins(tmp_path)
        assert "no_register" not in plugins


class TestRunPluginDetectors:
    def test_run_single_plugin(self, tmp_path):
        _make_plugin(tmp_path, "myplugin", """
            def register():
                return {"myplugin": find_myplugin}

            def find_myplugin(root, docs):
                return [{"file": "README.md", "version": "1.0"}]
        """)
        plugins = load_plugins(tmp_path)
        results = run_plugin_detectors(tmp_path, {"README.md": "test"}, plugins)
        assert "plugin_myplugin_drifts" in results
        assert len(results["plugin_myplugin_drifts"]) == 1

    def test_empty_plugins(self, tmp_path):
        results = run_plugin_detectors(tmp_path, {}, {})
        assert results == {}

    def test_plugin_failure_doesnt_crash(self, tmp_path):
        _make_plugin(tmp_path, "crasher", """
            def register():
                return {"crasher": find_crasher}

            def find_crasher(root, docs):
                raise RuntimeError("plugin crashed!")
        """)
        plugins = load_plugins(tmp_path)
        # Should not raise, just skip the failed plugin
        results = run_plugin_detectors(tmp_path, {}, plugins)
        assert "plugin_crasher_drifts" not in results


class TestPluginEndToEnd:
    def test_plugin_in_scan_repo(self, tmp_path):
        # Create a plugin file directly with proper escaping
        plugins_dir = tmp_path / ".driftcheck_plugins"
        plugins_dir.mkdir(exist_ok=True)
        # Use a simple string-based detector to avoid ruff escape-sequence warnings
        plugin_code = (
            "def register():\n"
            "    return {'custom': find_custom_drift}\n\n"
            "def find_custom_drift(root, docs):\n"
            "    drifts = []\n"
            "    for fname, content in docs.items():\n"
            "        if '1.0' in content:\n"
            "            drifts.append({\n"
            "                'file': fname,\n"
            "                'doc_version': '1.0',\n"
            "                'detail': 'custom 1.0 mentioned'\n"
            "            })\n"
            "    return drifts\n"
        )
        (plugins_dir / "custom.py").write_text(plugin_code)
        (tmp_path / "README.md").write_text("Uses custom 1.0 for testing")
        from driftcheck.detector import scan_repo
        result = scan_repo(tmp_path)
        assert "plugin_custom_drifts" in result
        assert len(result["plugin_custom_drifts"]) == 1
        assert result["plugin_custom_drifts"][0]["doc_version"] == "1.0"


class TestCustomDetectorsConfig:
    """Tests for custom_detectors config option (issue #209)."""

    def test_custom_detectors_paths_loaded(self, tmp_path):
        """Plugins listed in custom_detectors config paths are loaded."""
        # Create a custom detector file outside .driftcheck_plugins
        detector_file = tmp_path / "my_detector.py"
        detector_file.write_text(
            "import re\n\n"
            "def register():\n"
            "    return {'mydet': find_mydet_drift}\n\n"
            "def find_mydet_drift(root, docs):\n"
            "    return [{'file': 'README.md', 'detail': 'found by mydet'}]\n"
        )
        (tmp_path / "README.md").write_text("test")
        (tmp_path / ".driftcheck.toml").write_text(
            '[driftcheck]\ncustom_detectors = ["my_detector.py"]\n'
        )
        from driftcheck.detector import scan_repo
        result = scan_repo(tmp_path)
        assert "plugin_mydet_drifts" in result
        assert result["plugin_mydet_drifts"][0]["detail"] == "found by mydet"

    def test_custom_detectors_absolute_path(self, tmp_path):
        """Absolute paths in custom_detectors work."""
        # Create detector in a separate directory
        ext_dir = tmp_path / "external"
        ext_dir.mkdir()
        detector_file = ext_dir / "ext_detector.py"
        detector_file.write_text(
            "def register():\n"
            "    return {'ext': find_ext_drift}\n\n"
            "def find_ext_drift(root, docs):\n"
            "    return [{'file': 'test', 'detail': 'external'}]\n"
        )
        (tmp_path / "README.md").write_text("test")
        (tmp_path / ".driftcheck.toml").write_text(
            f'[driftcheck]\ncustom_detectors = ["{detector_file}"]\n'
        )
        from driftcheck.detector import scan_repo
        result = scan_repo(tmp_path)
        assert "plugin_ext_drifts" in result

    def test_custom_detectors_empty_default(self, tmp_path):
        """When custom_detectors is not set, no extra plugins loaded."""
        (tmp_path / "README.md").write_text("test")
        from driftcheck.detector import scan_repo
        result = scan_repo(tmp_path)
        # No plugin results should appear
        assert not any(k.startswith("plugin_") for k in result)
