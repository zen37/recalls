"""United States sources."""

from .fda import FdaSource

# The feeds polled for the US. Add another (e.g. USDA FSIS) as a new module here.
SOURCES = [FdaSource()]

__all__ = ["FdaSource", "SOURCES"]
