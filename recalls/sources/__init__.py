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


def sources_for(country: str, source: str | None = None) -> list[Source]:
    """The sources to poll for a country, or a clear error if unsupported.

    `source` narrows the result: a source name returns just that feed; None or
    "all" returns every feed for the country. An unknown name errors, listing the
    valid ones -- so a typo in a prod `--source` flag fails loudly, not silently.
    """
    try:
        country_sources = _REGISTRY[country]
    except KeyError:
        supported = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"no sources configured for country {country!r} "
            f"(supported: {supported}; set --country/RECALLS_COUNTRY)"
        )

    if source is None or source == "all":
        return country_sources

    selected = [s for s in country_sources if s.name == source]
    if not selected:
        available = ", ".join(s.name for s in country_sources) or "(none)"
        raise ValueError(
            f"no source {source!r} for country {country!r} "
            f"(available: {available}, or 'all')"
        )
    return selected


def countries() -> list[str]:
    return sorted(_REGISTRY)
