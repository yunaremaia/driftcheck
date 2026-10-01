"""Pytest fixtures for driftcheck tests."""

import os
import pathlib

import pytest
from pathlib import Path


@pytest.fixture
def temp_empty_repo(tmp_path: Path) -> Path:
    """Return a path to a fresh empty directory for testing detectors.

    Usage: def test_xxx(temp_empty_repo): ...
    """
    return tmp_path


class WinRenderedPath(str):
    """A relative path that *renders* like a Windows path.

    On Windows ``str(Path)`` yields backslashes, so code that stringifies a
    ``Path.relative_to()`` result instead of calling ``.as_posix()`` emits
    ``dir\\file`` there. That is invisible on POSIX, which is why such a bug
    only surfaces in the Windows CI legs.

    As a ``str`` subclass this drops into every consumer unchanged (JSON
    encoding, dict keys, f-strings, equality) while still answering the
    ``Path`` methods detectors call on the result. Only the rendering differs:
    ``str()`` gives backslashes like ``WindowsPath``, and ``as_posix()`` gives
    forward slashes like ``WindowsPath.as_posix()``.

    ``relative_to()`` results are only stringified or compared, never opened,
    so they need not carry filesystem behaviour.
    """

    def __new__(cls, posix_path):
        posix = str(posix_path)
        self = super().__new__(cls, posix.replace("/", "\\"))
        self._posix = posix
        self._real = posix_path
        return self

    def as_posix(self) -> str:
        """The forward-slash form, matching ``WindowsPath.as_posix()``."""
        return self._posix

    def __fspath__(self) -> str:
        return self._posix

    def __getattr__(self, name):
        # Delegate Path attributes (parts, name, suffix, ...) to the real path.
        return getattr(self._real, name)


@pytest.fixture
def windows_path(monkeypatch):
    """Make ``Path.relative_to()`` results render with Windows separators.

    Yields a callable that wraps a path (usually ``tmp_path``) into the root
    to hand to a detector. The patch is undone on teardown.

    On Windows the paths already render with backslashes, so the fixture is a
    no-op there: the same assertions then run against the real platform
    behaviour instead of a simulation of it.

    Patching ``relative_to`` rather than ``Path`` itself keeps this working
    across every Python version in the CI matrix: ``str()`` and
    ``__fspath__`` are used internally by ``glob()``/``iterdir()`` to reach
    the filesystem, and those internals were rewritten in 3.12, 3.13 and 3.14.
    """
    if os.name == "nt":
        # Real Windows already yields backslashes from str(); simulating on top
        # of that would double every separator.
        return Path

    original = pathlib.PurePath.relative_to

    def patched(self, *args, **kwargs):
        return WinRenderedPath(original(self, *args, **kwargs))

    monkeypatch.setattr(pathlib.PurePath, "relative_to", patched)
    return Path
