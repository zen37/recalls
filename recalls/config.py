"""Runtime config, assembled from the environment with sensible defaults.

Kept tiny on purpose. The one structural choice here is `country`: it selects
both which sources to poll (via the sources registry) and which per-country
database to write (``_data/<country>.db``) -- so a run is always scoped to one
jurisdiction, mirroring the per-country isolation on the store side.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_COUNTRY = "us"
DEFAULT_DATA_DIR = "_data"
DEFAULT_LANDING_DIR = "_landing"
DEFAULT_USER_AGENT = "recalls-alerts/0.1 (+https://github.com/zen37/recalls)"

# Which store backend to use. "sqlite" is the single-machine default; a cloud
# backend (e.g. "postgres") is added as a new adapter behind the AlertStore port.
DEFAULT_STORE_BACKEND = "sqlite"


def _default_db_path(country: str) -> str:
    """Per-country DB file, e.g. _data/us.db."""
    return os.path.join(DEFAULT_DATA_DIR, f"{country}.db")


@dataclass(frozen=True)
class Config:
    country: str = DEFAULT_COUNTRY
    db_path: str = _default_db_path(DEFAULT_COUNTRY)
    landing_dir: str = DEFAULT_LANDING_DIR
    user_agent: str = DEFAULT_USER_AGENT
    store_backend: str = DEFAULT_STORE_BACKEND
    # Optional override of a source's feed URL (single-source convenience; a
    # source falls back to its own default when this is None).
    feed_url: str | None = None
    # Which source(s) within the country to poll: a source name (e.g. "fda"),
    # the literal "all", or None (= all). `poll` sets this explicitly; the read
    # commands leave it None since they operate on the whole per-country store.
    source: str | None = None

    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        *,
        country: str | None = None,
        source: str | None = None,
    ) -> "Config":
        """Build config from the environment. `country` (e.g. a --country flag)
        overrides RECALLS_COUNTRY, which overrides the default. `source` (a
        --source flag) selects which feed(s) to poll; None means all."""
        env = env if env is not None else dict(os.environ)
        country = (country or env.get("RECALLS_COUNTRY", DEFAULT_COUNTRY)).lower()
        return cls(
            country=country,
            db_path=env.get("RECALLS_DB_PATH") or _default_db_path(country),
            landing_dir=env.get("RECALLS_LANDING_DIR", DEFAULT_LANDING_DIR),
            user_agent=env.get("RECALLS_USER_AGENT", DEFAULT_USER_AGENT),
            store_backend=env.get("RECALLS_STORE", DEFAULT_STORE_BACKEND),
            feed_url=env.get("RECALLS_FEED_URL") or None,
            source=(source.lower() if source else None),
        )
