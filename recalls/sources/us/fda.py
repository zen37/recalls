"""US — FDA Recalls, Market Withdrawals & Safety Alerts (RSS).

See docs/data-sources.md for the source's coverage and limits.
"""

from __future__ import annotations

import httpx

from ...config import Config
from ...models import Alert
from ..base import parse_rss

DEFAULT_FEED_URL = (
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml"
)


class FdaSource:
    name = "fda"
    country = "us"

    def feed_url(self, config: Config) -> str:
        return config.feed_url or DEFAULT_FEED_URL

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
