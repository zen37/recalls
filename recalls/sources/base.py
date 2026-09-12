"""Source port (interface) + shared RSS parsing.

A Source is the country-specific part of the app: it knows one official feed's
URL and shape, and turns it into the common ``Alert`` records the rest of the
app (store, dedupe, history, CLI) handles uniformly. Add a country/source by
adding a Source and registering it -- nothing downstream changes.
"""

from __future__ import annotations

import logging
from calendar import timegm
from datetime import datetime, timezone
from typing import Protocol

import feedparser

from ..config import Config
from ..models import Alert

logger = logging.getLogger("recalls.sources")


class Source(Protocol):
    """One official recall feed for one jurisdiction."""

    name: str      # source id stored on each alert, e.g. "fda"
    country: str   # ISO-ish country code, e.g. "us"

    def poll(self, config: Config) -> list[Alert]:
        """Fetch + parse the feed into Alerts (network)."""
        ...


def parse_rss(raw: bytes, *, source: str) -> list[Alert]:
    """Parse RSS bytes into Alerts. Reusable by any RSS-based Source.

    Skips entries with no stable id (guid/link) -- there is nothing to dedupe on.
    """
    parsed = feedparser.parse(raw)
    alerts: list[Alert] = []
    for entry in parsed.entries:
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


def _iso_published(entry) -> str:
    """Normalize an entry's publish time to an ISO-8601 UTC string, or ""."""
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return ""
    return datetime.fromtimestamp(timegm(tm), tz=timezone.utc).isoformat()
