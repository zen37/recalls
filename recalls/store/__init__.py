"""Store package: the AlertStore port, its adapters, and a factory.

Import the port and shared types from here; pick a backend with ``open_store``.
Adding a cloud backend later means a new adapter module + one branch here --
no change to the rest of the app.
"""

from __future__ import annotations

from ..config import Config
from .base import AlertStore, HistoryEntry, SyncResult, content_hash
from .sqlite import SqliteAlertStore

__all__ = [
    "AlertStore",
    "HistoryEntry",
    "SyncResult",
    "content_hash",
    "SqliteAlertStore",
    "open_store",
]


def open_store(config: Config) -> AlertStore:
    """Return the configured store backend (default: SQLite)."""
    backend = config.store_backend
    if backend == "sqlite":
        return SqliteAlertStore(config.db_path)
    # Future: "postgres" -> PostgresAlertStore(config.store_dsn), etc.
    raise ValueError(
        f"unknown store backend {backend!r} "
        f"(set RECALLS_STORE to a supported backend, e.g. 'sqlite')"
    )
