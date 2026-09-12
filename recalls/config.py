"""Runtime config, assembled from the environment with sensible defaults.

Kept tiny on purpose -- a real-time poller needs a feed URL, somewhere to store
alerts, and a polite User-Agent. Everything else is a later concern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# FDA "Recalls, Market Withdrawals & Safety Alerts" feed -- the lead source.
DEFAULT_FEED_URL = (
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml"
)
DEFAULT_DB_PATH = "_data/recalls.db"
DEFAULT_USER_AGENT = "recalls-alerts/0.1 (+https://github.com/zen37/recalls)"

# Which store backend to use. "sqlite" is the single-machine default; a cloud
# backend (e.g. "postgres") is added as a new adapter behind the AlertStore port.
DEFAULT_STORE_BACKEND = "sqlite"

# Which feed a stored alert came from. One source today; a column so more can be
# added without a migration.
SOURCE_FDA = "fda"


@dataclass(frozen=True)
class Config:
    feed_url: str = DEFAULT_FEED_URL
    db_path: str = DEFAULT_DB_PATH
    user_agent: str = DEFAULT_USER_AGENT
    source: str = SOURCE_FDA
    store_backend: str = DEFAULT_STORE_BACKEND

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = env if env is not None else dict(os.environ)
        return cls(
            feed_url=env.get("RECALLS_FEED_URL", DEFAULT_FEED_URL),
            db_path=env.get("RECALLS_DB_PATH", DEFAULT_DB_PATH),
            user_agent=env.get("RECALLS_USER_AGENT", DEFAULT_USER_AGENT),
            store_backend=env.get("RECALLS_STORE", DEFAULT_STORE_BACKEND),
        )
