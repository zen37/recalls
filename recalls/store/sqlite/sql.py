"""SQL for the SQLite adapter, separated from the adapter logic.

All SQLite dialect lives here (``AUTOINCREMENT``, ``strftime(... 'now')``,
``?`` placeholders, lookup-then-write upsert). A different backend gets its own
``*_sql.py`` in its own dialect; ``sqlite.py`` stays focused on the classify
new/updated/unchanged logic.
"""

from __future__ import annotations

# Portable timestamp expression (ISO-8601 UTC) reused wherever a row is stamped.
NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"

# -- Schema (DDL) ---------------------------------------------------------------

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS alerts (
    guid          TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    link          TEXT NOT NULL,
    published     TEXT,
    summary       TEXT,
    source        TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    first_seen    TEXT NOT NULL DEFAULT ({NOW}),
    last_updated  TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_published ON alerts (published DESC);

-- Append-only audit log: one snapshot per new/updated event, so the full
-- content at each change is preserved and consecutive rows can be diffed.
CREATE TABLE IF NOT EXISTS alerts_history (
    history_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    guid          TEXT NOT NULL,
    change_type   TEXT NOT NULL,       -- 'new' | 'updated'
    title         TEXT NOT NULL,
    link          TEXT NOT NULL,
    published     TEXT,
    summary       TEXT,
    content_hash  TEXT NOT NULL,
    changed_at    TEXT NOT NULL DEFAULT ({NOW})
);
CREATE INDEX IF NOT EXISTS idx_history_guid ON alerts_history (guid, history_id);
"""

# -- Migration ------------------------------------------------------------------

TABLE_INFO = "PRAGMA table_info(alerts)"
ADD_CONTENT_HASH = "ALTER TABLE alerts ADD COLUMN content_hash TEXT"
ADD_LAST_UPDATED = "ALTER TABLE alerts ADD COLUMN last_updated TEXT"

SELECT_ROWS_MISSING_HASH = (
    "SELECT guid, title, link, published, summary, source "
    "FROM alerts WHERE content_hash IS NULL"
)
SET_CONTENT_HASH = "UPDATE alerts SET content_hash = ? WHERE guid = ?"

# Seed a baseline 'new' history row for any alert with no history yet (rows
# stored before alerts_history existed), stamped at first_seen so the timeline
# stays truthful rather than collapsing to "now".
SEED_HISTORY_FOR_UNTRACKED = """
INSERT INTO alerts_history
    (guid, change_type, title, link, published, summary, content_hash, changed_at)
SELECT a.guid, 'new', a.title, a.link, a.published, a.summary,
       a.content_hash, a.first_seen
FROM alerts a
LEFT JOIN alerts_history h ON h.guid = a.guid
WHERE h.guid IS NULL
"""

# -- Sync (reads + writes) ------------------------------------------------------

SELECT_HASH_BY_GUID = "SELECT content_hash FROM alerts WHERE guid = ?"

INSERT_ALERT = """
INSERT INTO alerts
    (guid, title, link, published, summary, source, content_hash)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

UPDATE_ALERT = f"""
UPDATE alerts
SET title = ?, link = ?, published = ?, summary = ?,
    content_hash = ?, last_updated = {NOW}
WHERE guid = ?
"""

INSERT_HISTORY = """
INSERT INTO alerts_history
    (guid, change_type, title, link, published, summary, content_hash)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# -- Reads ----------------------------------------------------------------------

SELECT_RECENT = """
SELECT guid, title, link, published, summary, source
FROM alerts
ORDER BY published DESC, first_seen DESC
LIMIT ?
"""

# Case-insensitive substring match on guid or title (the `?` are the same
# "%query%" pattern passed twice).
SEARCH_ALERTS = """
SELECT guid, title, link, published, summary, source
FROM alerts
WHERE lower(guid) LIKE ? OR lower(title) LIKE ?
ORDER BY published DESC, first_seen DESC
LIMIT ?
"""

# history() appends an optional "WHERE guid = ?" and always an ORDER/LIMIT tail.
SELECT_HISTORY = (
    "SELECT history_id, guid, change_type, title, link, published, summary, changed_at "
    "FROM alerts_history"
)
HISTORY_WHERE_GUID = " WHERE guid = ?"
HISTORY_ORDER_LIMIT = " ORDER BY history_id DESC LIMIT ?"

SELECT_GUID_BY_HISTORY_ID = "SELECT guid FROM alerts_history WHERE history_id = ?"

COUNT_ALERTS = "SELECT COUNT(*) FROM alerts"
