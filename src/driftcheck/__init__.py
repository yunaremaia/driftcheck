"""driftcheck — detect version drift between docs and toolchain."""
__version__ = "0.1.44"

from .sarif import to_sarif

__all__ = ["to_sarif"]
