"""United States sources."""

from .fda import FdaSource
from .fsis import FsisSource

# The feeds polled for the US:
#   FDA  — produce/dairy/packaged foods, drugs, cosmetics
#   FSIS — USDA meat, poultry, processed egg products
SOURCES = [FdaSource(), FsisSource()]

__all__ = ["FdaSource", "FsisSource", "SOURCES"]
