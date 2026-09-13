"""One poll cycle: for the configured country, poll each source -> store -> log.

This is the unit a scheduler (cron/systemd) runs on an interval. It returns the
newly detected alerts so a future notifier seam can act on exactly them. A run
is scoped to one country (its sources, its per-country store).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import Config
from .landing import Landing
from .models import Alert
from .sources import sources_for
from .store.base import AlertStore

logger = logging.getLogger("recalls.poll")


@dataclass
class PollResult:
    fetched: int
    new: list[Alert]
    updated: list[Alert] = field(default_factory=list)
    # True when we may have fallen behind a feed's rolling window: the store was
    # non-empty, yet every item fetched (across the country's sources) was unseen.
    # Items could have scrolled off a window between polls without being captured
    # (see README / "polling cadence"). Not raised on a cold start (empty store).
    possible_gap: bool = False
    # Sources that failed this cycle, as "<source>: <reason>". A failing source
    # is logged and skipped so the others still complete -- one feed being down
    # (e.g. a 403 from its CDN) must not suppress alerts from the healthy feeds.
    errors: list[str] = field(default_factory=list)


def poll_once(config: Config, store: AlertStore, landing: Landing) -> PollResult:
    prior_count = store.count()
    fetched = 0
    new: list[Alert] = []
    updated: list[Alert] = []
    errors: list[str] = []

    for source in sources_for(config.country, config.source):
        try:
            raw = source.fetch(config)
            landing.land(config.country, source.name, raw)  # raw kept before parsing
            alerts = source.parse(raw)
            result = store.sync(alerts)
        except Exception as exc:
            # Isolate per source: a failing feed (network error, CDN 403, bad
            # payload) is logged and skipped so the remaining sources still run.
            errors.append(f"{source.name}: {exc}")
            logger.warning(
                "poll source failed country=%s source=%s -- skipping: %s",
                config.country, source.name, exc,
            )
            continue
        fetched += len(alerts)
        new.extend(result.new)
        updated.extend(result.updated)
        logger.info(
            "poll country=%s source=%s fetched=%s new=%s updated=%s",
            config.country, source.name, len(alerts), len(result.new), len(result.updated),
        )
        for a in result.new:
            logger.info("NEW ALERT [%s] %s -- %s", a.published or "?", a.title, a.link)
        for a in result.updated:
            logger.info("UPDATED ALERT [%s] %s -- %s", a.published or "?", a.title, a.link)

    logger.info(
        "poll complete country=%s fetched=%s new=%s updated=%s failed=%s total_stored=%s",
        config.country, fetched, len(new), len(updated), len(errors), store.count(),
    )

    possible_gap = prior_count > 0 and fetched > 0 and len(new) == fetched
    if possible_gap:
        logger.warning(
            "possible gap country=%s: all %s fetched items were new against a "
            "non-empty store -- older items may have scrolled off a feed window "
            "between polls; consider polling more frequently or backfilling from a "
            "complete source",
            config.country, fetched,
        )

    return PollResult(
        fetched=fetched, new=new, updated=updated, possible_gap=possible_gap, errors=errors
    )
