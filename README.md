# recalls

Near-real-time **consumer recall alerts**. Polls official recall feeds, detects
newly published alerts, and stores them — so a consumer learns about a recall the
day it is announced ("is this in my fridge?"), not weeks later.

```
FDA Recalls RSS ──▶ fetch ──▶ parse ──▶ classify new / updated / unchanged ──▶ store (SQLite) ──▶ list
                                          (dedupe on guid, content-hash change)
```

**Lead source:** the FDA "Recalls, Market Withdrawals & Safety Alerts" RSS feed —
same-day announcements covering FDA-regulated foods (produce, dairy, packaged
foods), drugs, and cosmetics. Every source is cataloged per country in
[`docs/data-sources.md`](docs/data-sources.md).

## Scope

This is the **timely alerts** product — thin, fast, actionable. It is deliberately
*not* a data platform: no medallion lake, no classification/severity enrichment,
no cross-country analytics. That structured/historical side lives in the sibling
[`recalls-os`](https://github.com/zen37/recalls-os) repo. When the two meet, an
alert here can be enriched later by the enforcement record `recalls-os` holds.

Each poll classifies every fetched item as **new** (guid never seen), **updated**
(guid seen but content changed — e.g. FDA expanded the affected lots or flipped
status to terminated), or **unchanged** (identical repeat → ignored). "Changed"
is decided by a content hash of title/link/published/summary; the store keeps a
`last_updated` timestamp per alert alongside `first_seen`.

Every new/updated event is also appended to an **`alerts_history`** table — a
snapshot of the content at each change — so you can see *what* changed over time,
not just that it did. The `alerts` table holds the current state; `alerts_history`
holds the audit trail. View it with:

```bash
uv run python -m recalls history                # recent change events
uv run python -m recalls history <guid-url>     # one alert's full timeline
```

First cut (this repo): **ingest + detect new/updated**. A notifier (email/push/webhook)
and a read API/UI are clean seams left for later.

## Run

```bash
uv sync
cp .env.example .env          # optional; sensible defaults otherwise
uv run python -m recalls poll   # fetch once, store new alerts, log what's new
uv run python -m recalls list   # show recent stored alerts
uv run pytest                   # tests (offline; RSS fixture)
```

Poll on a schedule with cron/systemd, e.g. every 15 min:

```
*/15 * * * * cd /path/to/recalls && uv run python -m recalls poll >> poll.log 2>&1
```

### Polling cadence & the window-gap warning

The feed is a **rolling window** of only the ~20 most recent announcements: an
item scrolls off the bottom once ~20 newer ones push in. You miss a recall only
if *more than a full window* is published between two polls — so poll often
(15 min / hourly) relative to publication volume (a handful of food recalls a
day → huge margin).

As a safety net, a poll that finds **every** fetched item is new against a
**non-empty** store logs a `possible gap` warning and sets
`PollResult.possible_gap` — the signal you may have fallen behind and lost older
items to the window. (An all-new *cold start* against an empty store is normal
and does not warn.) Capturing full history is out of scope here by design — that
is the paged-backfill job of the sibling [`recalls-os`](https://github.com/zen37/recalls-os).

## Layout

```
recalls/
  config.py    country, per-country db path, user-agent, log level (from .env)
  models.py    Alert — the thin alert record
  sources/     per-country feeds (the code that differs by country)
    base.py      Source Protocol + shared RSS parsing
    __init__.py  country -> sources registry; sources_for(country)
    us/          United States
      fda.py       FdaSource (FDA Recalls RSS)
      __init__.py  SOURCES = [FdaSource()]
    ca/          Canada — skeleton to fill in (see "Adding a country")
      cfia.py      CfiaSource stub (not implemented)
      __init__.py  SOURCES = []
  store/       AlertStore port + adapters (swap the backend, don't rewrite)
    base.py      AlertStore Protocol + SyncResult / HistoryEntry + content_hash
    __init__.py  open_store(config) factory -> picks the backend
    sqlite/      the SQLite backend (default)
      adapter.py   SqliteAlertStore: alerts + alerts_history logic
      sql.py       all SQLite SQL/DDL as named constants (dialect isolated here)
      __init__.py  exports SqliteAlertStore
    # a cloud backend later is a sibling folder, e.g. postgres/
  poll.py      one poll cycle: for the country, poll each source -> store -> log
  cli.py       `poll` / `list` / `history`
tests/         offline parse + dedupe + factory tests over an RSS fixture
```

A run is scoped to one **country**: it polls that country's sources and writes
to its own database, `_data/<country>.db` (e.g. `_data/us.db`) — gitignored. The
country comes from `--country`, else `RECALLS_COUNTRY`, else the default `us`:

```bash
uv run python -m recalls poll                 # default: us
uv run python -m recalls poll --country ca     # explicit (best for cron)
```

### Adding a country

The store, dedupe, history, and CLI are country-agnostic — only the feed differs.
`sources/ca/` is a ready-made skeleton (Canada). To add a country `<cc>`:

1. In `sources/<cc>/`, implement a `Source` (see `us/fda.py` for the pattern;
   reuse `sources/base.parse_rss` if the feed is RSS) and export it from the
   package's `SOURCES` list.
2. Register it in `sources/__init__.py`'s `_REGISTRY` (`"<cc>": <cc>.SOURCES`).
3. Document the feed in [`docs/data-sources.md`](docs/data-sources.md).

Then `RECALLS_COUNTRY=<cc> uv run python -m recalls poll` writes `_data/<cc>.db`.
No changes to the store, poll loop, or CLI.
