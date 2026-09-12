"""SQLite adapter for the AlertStore port (the single-machine default).

Each poll classifies every fetched item as one of three:

- **new**       -- guid never seen before          -> insert
- **updated**   -- guid seen, but content changed   -> update + stamp last_updated
- **unchanged** -- guid seen, content identical     -> no-op

Two tables: ``alerts`` holds current state (one row per guid); ``alerts_history``
is an append-only audit log with a content snapshot per new/updated event.

The SQL itself lives in ``sqlite_sql.py``; this module is the logic that runs it.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing

from ...models import Alert
from ..base import HistoryEntry, SyncResult, content_hash
from . import sql

logger = logging.getLogger("recalls.store.sqlite")


class SqliteAlertStore:
    """AlertStore backed by a local SQLite file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(sql.SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add columns missing from an older DB, then backfill content_hash.

        Backfilling means existing rows don't all falsely count as "updated" on
        the first poll after upgrading.
        """
        cols = {r["name"] for r in conn.execute(sql.TABLE_INFO)}
        if not cols:
            return  # fresh DB -- schema already current
        if "content_hash" not in cols:
            conn.execute(sql.ADD_CONTENT_HASH)
        if "last_updated" not in cols:
            conn.execute(sql.ADD_LAST_UPDATED)
        for r in conn.execute(sql.SELECT_ROWS_MISSING_HASH).fetchall():
            conn.execute(sql.SET_CONTENT_HASH, (content_hash(_row_to_alert(r)), r["guid"]))
        conn.execute(sql.SEED_HISTORY_FOR_UNTRACKED)

    def sync(self, alerts: list[Alert]) -> SyncResult:
        result = SyncResult()
        if not alerts:
            return result
        with closing(self._connect()) as conn, conn:
            for a in alerts:
                h = content_hash(a)
                row = conn.execute(sql.SELECT_HASH_BY_GUID, (a.guid,)).fetchone()
                if row is None:
                    conn.execute(
                        sql.INSERT_ALERT,
                        (a.guid, a.title, a.link, a.published, a.summary, a.source, h),
                    )
                    self._record_history(conn, a, "new", h)
                    result.new.append(a)
                elif row["content_hash"] != h:
                    conn.execute(
                        sql.UPDATE_ALERT,
                        (a.title, a.link, a.published, a.summary, h, a.guid),
                    )
                    self._record_history(conn, a, "updated", h)
                    result.updated.append(a)
                # else: unchanged -> no-op
        return result

    @staticmethod
    def _record_history(
        conn: sqlite3.Connection, alert: Alert, change_type: str, h: str
    ) -> None:
        conn.execute(
            sql.INSERT_HISTORY,
            (alert.guid, change_type, alert.title, alert.link, alert.published,
             alert.summary, h),
        )

    def history(self, guid: str | None = None, limit: int = 50) -> list[HistoryEntry]:
        query = sql.SELECT_HISTORY
        params: list = []
        if guid:
            query += sql.HISTORY_WHERE_GUID
            params.append(guid)
        query += sql.HISTORY_ORDER_LIMIT
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            HistoryEntry(
                history_id=r["history_id"],
                guid=r["guid"],
                change_type=r["change_type"],
                title=r["title"],
                link=r["link"],
                published=r["published"] or "",
                summary=r["summary"] or "",
                changed_at=r["changed_at"],
            )
            for r in rows
        ]

    def guid_of(self, history_id: int) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(sql.SELECT_GUID_BY_HISTORY_ID, (history_id,)).fetchone()
        return row["guid"] if row else None

    def recent(self, limit: int = 20) -> list[Alert]:
        with closing(self._connect()) as conn:
            rows = conn.execute(sql.SELECT_RECENT, (limit,)).fetchall()
        return [_row_to_alert(r) for r in rows]

    def find_alerts(self, query: str, limit: int = 50) -> list[Alert]:
        pattern = f"%{query.lower()}%"
        with closing(self._connect()) as conn:
            rows = conn.execute(sql.SEARCH_ALERTS, (pattern, pattern, limit)).fetchall()
        return [_row_to_alert(r) for r in rows]

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute(sql.COUNT_ALERTS).fetchone()[0])


def _row_to_alert(r: sqlite3.Row) -> Alert:
    return Alert(
        guid=r["guid"],
        title=r["title"],
        link=r["link"],
        published=r["published"] or "",
        summary=r["summary"] or "",
        source=r["source"],
    )
