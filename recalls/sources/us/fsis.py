"""US — USDA FSIS Recalls & Public Health Alerts (RSS).

The second US feed alongside FDA: FSIS regulates **meat, poultry, and processed
egg products**, a different agency from the FDA with its own same-day recall
feed. Its RSS is shaped exactly like the FDA feed (item = title/link/description/
pubDate/guid, guid is the permalink), so parsing reuses ``base.parse_rss`` with
no FSIS-specific code.

See docs/data-sources.md for the source's coverage and limits.
"""

from __future__ import annotations

from curl_cffi import requests as curl_requests

from ...config import Config
from ...models import Alert
from ..base import parse_rss

DEFAULT_FEED_URL = "https://www.fsis.usda.gov/fsis-content/rss/recalls.xml"

# The FSIS feed is behind Akamai Bot Manager, which blocks (403) clients whose
# TLS/HTTP-2 fingerprint doesn't match a real browser -- a plain httpx/requests
# UA change does not help. curl_cffi with ``impersonate`` replays Chrome's actual
# TLS handshake, so the request looks like the browser that loads the feed fine.
_IMPERSONATE = "chrome"


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
        # Note: we rely on curl_cffi's browser-matched headers (from impersonate)
        # rather than forcing config.user_agent -- overriding the UA alone would
        # desync it from the TLS fingerprint and re-trip the bot check.
        resp = curl_requests.get(
            self.feed_url(config),
            impersonate=_IMPERSONATE,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.content

    def parse(self, raw: bytes) -> list[Alert]:
        return parse_rss(raw, source=self.name)

    def poll(self, config: Config) -> list[Alert]:
        return self.parse(self.fetch(config))
