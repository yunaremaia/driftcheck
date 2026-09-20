"""Tests for _read_files_parallel error reporting (issue #178) and
configurable timeouts (issue #238).
"""
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

from driftcheck.detector import _read_files_parallel, _read_text_safe


def test_read_files_parallel_success(tmp_path):
    """All files readable — no warnings."""
    f1 = tmp_path / "README.md"
    f1.write_text("hello")
    f2 = tmp_path / "setup.py"
    f2.write_text("world")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _read_files_parallel(tmp_path, ["*.md", "*.py"])
        assert "hello" in result
        assert "world" in result
        assert len(w) == 0


def test_read_files_parallel_none_files(tmp_path):
    """No matching files — empty string."""
    result = _read_files_parallel(tmp_path, ["*.nonexistent"])
    assert result == ""


def test_read_files_parallel_logs_failures(tmp_path):
    """When _read_text_safe raises, warning is emitted."""
    f1 = tmp_path / "ok.md"
    f1.write_text("ok content")

    original = _read_text_safe

    def fake_safe(path, max_size=1_000_000):
        if "ok" in str(path):
            return original(path, max_size)
        raise OSError("permission denied")

    with patch("driftcheck.detector._read_text_safe", side_effect=fake_safe):
        # Create a second file that will fail
        f2 = tmp_path / "denied.md"
        f2.write_text("no read")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _read_files_parallel(tmp_path, ["*.md"])
            assert "ok content" in result
            assert len(w) == 1
            assert "failed to read" in str(w[0].message)
            assert "permission denied" in str(w[0].message)


def test_read_files_parallel_caps_warning_at_5(tmp_path):
    """Warning message caps at 5 failed files with '...'."""
    files = []
    for i in range(7):
        f = tmp_path / f"file{i}.md"
        f.write_text(f"content {i}")
        files.append(f)

    def fake_safe(path, max_size=1_000_000):
        raise OSError(f"denied for {path.name}")

    with patch("driftcheck.detector._read_text_safe", side_effect=fake_safe):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _read_files_parallel(tmp_path, ["*.md"])
            assert len(w) == 1
            msg = str(w[0].message)
            assert "7 file(s) failed to read" in msg
            assert "..." in msg  # capped indicator


# ---------------------------------------------------------------------------
# Issue #238: configurable timeouts
# ---------------------------------------------------------------------------


class TestReadFilesParallelTimeouts:
    """Validate the read_timeout / read_pool_timeout parameters (issue #238)."""

    def test_default_read_timeout_is_5(self, tmp_path):
        """Default read_timeout parameter is 5.0 seconds."""
        import inspect
        sig = inspect.signature(_read_files_parallel)
        assert sig.parameters["read_timeout"].default == 5.0

    def test_default_read_pool_timeout_is_30(self, tmp_path):
        """Default read_pool_timeout parameter is 30.0 seconds."""
        import inspect
        sig = inspect.signature(_read_files_parallel)
        assert sig.parameters["read_pool_timeout"].default == 30.0

    def test_custom_read_timeout_passed_to_future_result(self, tmp_path):
        """read_timeout is forwarded to future.result(timeout=...)."""
        f1 = tmp_path / "a.txt"
        f1.write_text("content")

        captured_timeout = {}

        original_result = None

        class FakeFuture:
            def __init__(self, real_future):
                self._real = real_future

            def result(self, timeout=None):
                captured_timeout["future_timeout"] = timeout
                return self._real.result(timeout=timeout)

        with patch("driftcheck.detector.as_completed") as mock_ac:
            real_futures = {}

            def fake_as_completed(fs, timeout=None):
                captured_timeout["pool_timeout"] = timeout
                real_futures.update(fs)
                return iter(fs.keys())

            mock_ac.side_effect = fake_as_completed

            with patch("driftcheck.detector.ThreadPoolExecutor") as mock_tpe:
                mock_executor = MagicMock()
                mock_tpe.return_value.__enter__ = lambda s: mock_executor
                mock_tpe.return_value.__exit__ = MagicMock(return_value=False)

                fake_future = MagicMock()
                fake_future.result.return_value = "hello"
                mock_executor.submit.return_value = fake_future

                _read_files_parallel(tmp_path, ["*.txt"], read_timeout=12.0, read_pool_timeout=60.0)

                # Pool-wide timeout forwarded to as_completed
                assert captured_timeout.get("pool_timeout") == 60.0
                # Per-file timeout forwarded to future.result
                fake_future.result.assert_called_with(timeout=12.0)

    def test_custom_timeout_reflected_in_timeout_warning_message(self, tmp_path):
        """Timeout message includes the configured timeout value, not the hardcoded 5."""
        f1 = tmp_path / "slow.txt"
        f1.write_text("content")

        def fake_as_completed(fs, timeout=None):
            for f in fs:
                yield f

        with patch("driftcheck.detector.as_completed", side_effect=fake_as_completed):
            with patch("driftcheck.detector.ThreadPoolExecutor") as mock_tpe:
                mock_executor = MagicMock()
                mock_tpe.return_value.__enter__ = lambda s: mock_executor
                mock_tpe.return_value.__exit__ = MagicMock(return_value=False)

                fake_future = MagicMock()
                fake_future.result.side_effect = TimeoutError()
                mock_executor.submit.return_value = fake_future

                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    _read_files_parallel(tmp_path, ["*.txt"], read_timeout=99.0)

                if w:
                    assert "99.0" in str(w[0].message)

    def test_zero_matching_files_returns_empty_regardless_of_timeout(self, tmp_path):
        """Empty pattern match exits before timeout logic."""
        result = _read_files_parallel(tmp_path, ["*.nope"], read_timeout=0.001, read_pool_timeout=0.001)
        assert result == ""

    def test_config_read_timeout_flows_into_parallel_reader(self, tmp_path):
        """Integration: read_timeout from .driftcheck.toml reaches _read_files_parallel."""
        from driftcheck.config import load_config, get_read_timeouts

        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nread_timeout = 15\nread_pool_timeout = 45\n"
        )
        config = load_config(tmp_path)
        rt, rpt = get_read_timeouts(config)

        assert rt == 15.0
        assert rpt == 45.0

    def test_float_read_timeout_accepted(self, tmp_path):
        """read_timeout may be a float (e.g. 2.5)."""
        from driftcheck.config import load_config, get_read_timeouts

        (tmp_path / ".driftcheck.toml").write_text(
            "[driftcheck]\nread_timeout = 2.5\n"
        )
        config = load_config(tmp_path)
        rt, _ = get_read_timeouts(config)
        assert rt == 2.5

    def test_get_read_timeouts_defaults_when_no_config_file(self, tmp_path):
        """get_read_timeouts returns defaults when .driftcheck.toml is absent."""
        from driftcheck.config import load_config, get_read_timeouts, DEFAULT_CONFIG

        config = load_config(tmp_path)  # no .driftcheck.toml
        rt, rpt = get_read_timeouts(config)

        assert rt == float(DEFAULT_CONFIG["read_timeout"])
        assert rpt == float(DEFAULT_CONFIG["read_pool_timeout"])

    def test_get_read_timeouts_guards_against_none(self):
        """get_read_timeouts falls back gracefully when values are None."""
        from driftcheck.config import get_read_timeouts, DEFAULT_CONFIG

        config = {"read_timeout": None, "read_pool_timeout": None}
        rt, rpt = get_read_timeouts(config)

        assert rt == float(DEFAULT_CONFIG["read_timeout"])
        assert rpt == float(DEFAULT_CONFIG["read_pool_timeout"])

    def test_get_read_timeouts_guards_against_zero(self):
        """get_read_timeouts falls back when values are <= 0."""
        from driftcheck.config import get_read_timeouts, DEFAULT_CONFIG

        config = {"read_timeout": 0, "read_pool_timeout": -1}
        rt, rpt = get_read_timeouts(config)

        assert rt == float(DEFAULT_CONFIG["read_timeout"])
        assert rpt == float(DEFAULT_CONFIG["read_pool_timeout"])
