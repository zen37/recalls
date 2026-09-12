"""Store port (interface) + shared, backend-agnostic types.

The whole app depends only on the ``AlertStore`` Protocol below, never on a
concrete backend. SQLite is the default adapter (``sqlite.SqliteAlertStore``);
a cloud backend (e.g. Postgres) is a new class implementing this same Protocol,
selected by ``store.open_store`` -- swap the backend, don't rewrite the app.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol

from ..models import Alert


def content_hash(alert: Alert) -> str:
    """Stable hash of the meaningful content of an alert.

    guid/source are identity, not content, so they are excluded -- a change in
    title/link/published/summary is what counts as an "update". Backend-agnostic
    so every adapter classifies new/updated/unchanged identically.
    """
    payload = "\x1f".join([alert.title, alert.link, alert.published, alert.summary])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class SyncResult:
    new: list[Alert] = field(default_factory=list)
    updated: list[Alert] = field(default_factory=list)


@dataclass(frozen=True)
class HistoryEntry:
    history_id: int       # short, stable per-event id (easier to reference than the guid)
    guid: str
    change_type: str      # 'new' | 'updated'
    title: str
    link: str
    published: str
    summary: str
    source: str
    changed_at: str


class AlertStore(Protocol):
    """What the app requires of any store backend."""

    def sync(self, alerts: list[Alert]) -> SyncResult:
        """Insert new alerts, update changed ones, ignore unchanged; return both
        the new and the updated sets. Idempotent on identical content."""
        ...

    def recent(self, limit: int = 20) -> list[Alert]:
        """Most recent stored alerts, newest publish date first."""
        ...

    def find_alerts(self, query: str, limit: int = 50) -> list[Alert]:
        """Alerts whose guid or title contains `query` (case-insensitive),
        newest publish date first. Lets a caller match a short substring of the
        URL/title instead of pasting the full guid."""
        ...

    def history(self, guid: str | None = None, limit: int = 50) -> list[HistoryEntry]:
        """Change events (new/updated), newest first; optionally one guid's timeline."""
        ...

    def guid_of(self, history_id: int) -> str | None:
        """The guid a history event belongs to, or None if the id is unknown.

        Lets a caller reference an alert by a short event id instead of its guid.
        """
        ...

    def count(self) -> int:
        """Number of distinct alerts currently stored."""
        ...
