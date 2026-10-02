"""Public API surface guarantees (issue #251 follow-up).

The public API is a supported contract: anything exported from
``driftcheck.__all__`` must be importable from the top-level package and
must not disappear in a refactor. ``scan_repo`` is the main entry point of
the tool, so exposing it as part of the library surface is not optional.
"""

import driftcheck
from driftcheck import __all__ as PUBLIC_API


def test_scan_repo_is_exported_from_the_top_level_package():
    """The main entry point must be part of the documented public API."""
    assert "scan_repo" in PUBLIC_API
    assert callable(driftcheck.scan_repo)


def test_every_exported_name_actually_exists():
    """A stale entry in __all__ is an AttributeError waiting to happen."""
    missing = [name for name in PUBLIC_API if not hasattr(driftcheck, name)]
    assert missing == [], f"__all__ advertises names that do not exist: {missing}"


def test_public_api_is_sorted_within_its_block():
    """Keeps diffs reviewable and avoids accidental duplicate entries."""
    assert len(PUBLIC_API) == len(set(PUBLIC_API)), "duplicated entry in __all__"
