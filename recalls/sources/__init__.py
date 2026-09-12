"""Sources package: the Source port and the country -> sources registry.

Each country is its own subpackage exposing a ``SOURCES`` list (see ``us/``).
Adding a jurisdiction:
  1. create ``sources/<cc>/`` with a Source module + a ``SOURCES`` list
     (``ca/`` is a ready-made skeleton to fill in),
  2. register it in ``_REGISTRY`` below.
`poll` asks this registry which feeds to pull for the configured country.
"""

from __future__ import annotations

from . import us
from .base import Source, parse_rss

__all__ = ["Source", "parse_rss", "sources_for", "countries"]

# Country code -> the official feeds we pull for it.
_REGISTRY: dict[str, list[Source]] = {
    "us": us.SOURCES,
    # "ca": ca.SOURCES,  # uncomment once sources/ca/ has a working source
}


def sources_for(country: str) -> list[Source]:
    """The sources to poll for a country, or a clear error if unsupported."""
    try:
        return _REGISTRY[country]
    except KeyError:
        supported = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"no sources configured for country {country!r} "
            f"(supported: {supported}; set RECALLS_COUNTRY)"
        )


def countries() -> list[str]:
    return sorted(_REGISTRY)
