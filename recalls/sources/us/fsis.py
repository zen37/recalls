"""US — USDA FSIS Recalls & Public Health Alerts (RSS).

The second US feed alongside FDA: FSIS regulates **meat, poultry, and processed
egg products**, a different agency from the FDA with its own same-day recall
feed. Its RSS is shaped exactly like the FDA feed (item = title/link/description/
pubDate/guid, guid is the permalink), so parsing reuses ``base.parse_rss`` with
no FSIS-specific code.

See docs/data-sources.md for the source's coverage and limits.
"""

from __future__ import annotations

import httpx

from ...config import Config
from ...models import Alert
from ..base import parse_rss

DEFAULT_FEED_URL = "https://www.fsis.usda.gov/fsis-content/rss/recalls.xml"


class FsisSource:
    name = "fsis"
    country = "us"

    def feed_url(self, config: Config) -> str:
        # FSIS always uses its own feed. The single ``config.feed_url`` override
        # is an FDA-era single-source convenience; honoring it here too would
        # point both US feeds at the same URL. Override FSIS via code/a future
        # per-source config key, not the shared RECALLS_FEED_URL.
        return DEFAULT_FEED_URL

    def fetch(self, config: Config, *, timeout: float = 30.0) -> bytes:
        resp = httpx.get(
            self.feed_url(config),
            headers={"User-Agent": config.user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content

    def parse(self, raw: bytes) -> list[Alert]:
        return parse_rss(raw, source=self.name)

    def poll(self, config: Config) -> list[Alert]:
        return self.parse(self.fetch(config))
