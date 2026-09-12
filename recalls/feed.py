"""Fetch and parse the recall RSS feed into Alert records.

Split in two so parsing is testable offline:
- ``fetch`` does the network call (httpx) and returns raw bytes.
- ``parse`` turns bytes into ``Alert``s (feedparser) with no network.

``poll`` composes them.
"""

from __future__ import annotations

import logging
from calendar import timegm
from datetime import datetime, timezone

import feedparser
import httpx

from .config import Config
from .models import Alert

logger = logging.getLogger("recalls.feed")


def fetch(config: Config, *, timeout: float = 30.0) -> bytes:
    """GET the feed and return the raw response bytes."""
    resp = httpx.get(
        config.feed_url,
        headers={"User-Agent": config.user_agent},
        timeout=timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content


def parse(raw: bytes, *, source: str) -> list[Alert]:
    """Parse feed bytes into Alerts. Skips entries with no stable id."""
    parsed = feedparser.parse(raw)
    alerts: list[Alert] = []
    for entry in parsed.entries:
        # feedparser maps RSS <guid> -> id, falling back to link.
        guid = (entry.get("id") or entry.get("link") or "").strip()
        if not guid:
            logger.warning("skipping feed entry with no guid/link: %r", entry.get("title"))
            continue
        alerts.append(
            Alert(
                guid=guid,
                title=(entry.get("title") or "").strip(),
                link=(entry.get("link") or "").strip(),
                published=_iso_published(entry),
                summary=(entry.get("summary") or "").strip(),
                source=source,
            )
        )
    return alerts


def poll_feed(config: Config) -> list[Alert]:
    """Fetch + parse in one call (network)."""
    return parse(fetch(config), source=config.source)


def _iso_published(entry) -> str:
    """Normalize the entry's publish time to an ISO-8601 UTC string.

    feedparser parses ``pubDate`` into ``published_parsed`` (a UTC struct_time);
    we render it as ISO. If the feed omitted a parseable date, return "".
    """
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return ""
    return datetime.fromtimestamp(timegm(tm), tz=timezone.utc).isoformat()
