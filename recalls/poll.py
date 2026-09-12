"""One poll cycle: fetch -> parse -> detect new -> store -> log.

This is the unit a scheduler (cron/systemd) runs on an interval. It returns the
newly detected alerts so a future notifier seam can act on exactly them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import Config
from .feed import poll_feed
from .models import Alert
from .store.base import AlertStore

logger = logging.getLogger("recalls.poll")


@dataclass
class PollResult:
    fetched: int
    new: list[Alert]
    updated: list[Alert] = field(default_factory=list)
    # True when we may have fallen behind the feed's rolling window: the store
    # was non-empty, yet every item fetched was unseen. That means items could
    # have scrolled off the window between polls without ever being captured
    # (see README / "polling cadence"). Not raised on a cold start (empty store),
    # where an all-new window is expected.
    possible_gap: bool = False


def poll_once(config: Config, store: AlertStore) -> PollResult:
    prior_count = store.count()
    alerts = poll_feed(config)
    result = store.sync(alerts)
    new, updated = result.new, result.updated
    logger.info(
        "poll source=%s fetched=%s new=%s updated=%s total_stored=%s",
        config.source,
        len(alerts),
        len(new),
        len(updated),
        store.count(),
    )
    for a in new:
        logger.info("NEW ALERT [%s] %s -- %s", a.published or "?", a.title, a.link)
    for a in updated:
        logger.info("UPDATED ALERT [%s] %s -- %s", a.published or "?", a.title, a.link)

    possible_gap = prior_count > 0 and len(alerts) > 0 and len(new) == len(alerts)
    if possible_gap:
        logger.warning(
            "possible gap source=%s: all %s fetched items were new against a "
            "non-empty store -- older items may have scrolled off the feed window "
            "between polls; consider polling more frequently or backfilling from a "
            "complete source",
            config.source,
            len(alerts),
        )

    return PollResult(
        fetched=len(alerts), new=new, updated=updated, possible_gap=possible_gap
    )
