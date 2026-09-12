"""Canada — Health Canada / CFIA recalls  (SKELETON — not implemented yet).

Starting point for Canada support. To implement:

1. Fill in the feed URL and the fetch/parse below (see ``us/fda.py`` for the
   pattern; if the Canadian feed is RSS you can reuse ``..base.parse_rss``).
2. Add this source to ``sources/ca/__init__.py``'s ``SOURCES`` list.
3. Register "ca" in the registry in ``sources/__init__.py``.

Source details (feed, format, coverage, limits): docs/data-sources.md#canada.
"""

from __future__ import annotations

from ...config import Config
from ...models import Alert

# TODO: the official Canadian recall feed URL (Health Canada / CFIA).
DEFAULT_FEED_URL = ""


class CfiaSource:
    name = "cfia"
    country = "ca"

    def fetch(self, config: Config) -> bytes:
        # TODO: GET DEFAULT_FEED_URL (honoring config.feed_url override).
        raise NotImplementedError(
            "Canada (CFIA) source not implemented yet -- see docs/data-sources.md#canada"
        )

    def parse(self, raw: bytes) -> list[Alert]:
        # TODO: parse raw into Alert records with source=self.name
        # (reuse ..base.parse_rss if the feed is RSS).
        raise NotImplementedError(
            "Canada (CFIA) source not implemented yet -- see docs/data-sources.md#canada"
        )
