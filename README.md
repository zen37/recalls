# recalls

Near-real-time **consumer recall alerts**. Polls official recall feeds, detects
newly published alerts, and stores them — so a consumer learns about a recall the
day it is announced ("is this in my fridge?"), not weeks later.

```
FDA Recalls RSS ─▶ fetch ─▶ land raw ─▶ parse ─▶ classify new/updated/unchanged ─▶ store (SQLite) ─▶ list
                            (audit/replay)         (dedupe on guid, content-hash)
```

**Lead source:** the FDA "Recalls, Market Withdrawals & Safety Alerts" RSS feed —
same-day announcements covering FDA-regulated foods (produce, dairy, packaged
foods), drugs, and cosmetics. The US also polls **USDA FSIS** (meat, poultry, and
processed egg products — the foods the FDA does not cover), whose feed is the same
RSS shape. Every source is cataloged per country in
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
uv run python -m recalls history --country us              # recent change events
uv run python -m recalls history --country us <guid-url>   # one alert's full timeline
```

First cut (this repo): **ingest + detect new/updated**. A notifier (email/push/webhook)
and a read API/UI are clean seams left for later.

## Run

```bash
uv sync
cp .env.example .env                                   # optional; sensible defaults otherwise
uv run python -m recalls poll --country us --source fda    # fetch one feed, store new alerts
uv run python -m recalls poll --country us --source all    # every feed for the country
uv run python -m recalls list --country us                 # show recent stored alerts
uv run pytest                                           # tests (offline; RSS fixture)
```

`poll` requires an explicit `--country` and `--source` — no silent defaults on
the write path, so a prod/cron invocation always states exactly what it fetches.
`--source` is a source name (`fda`, `fsis`) or `all` for every feed of the
country. (`list`/`history` also require `--country`, so a read never silently
hits the wrong per-country db.)

Poll on a schedule with cron/systemd. Give each source its own line — sources can
warrant different cadences, and one feed being down must not delay another — e.g.
FDA every 15 min, FSIS every 30:

```
*/15 * * * * cd /path/to/recalls && uv run python -m recalls poll --country us --source fda  >> poll.log 2>&1
*/30 * * * * cd /path/to/recalls && uv run python -m recalls poll --country us --source fsis >> poll.log 2>&1
```

A single source failing is logged and skipped, and the run still exits 0 as long
as another source succeeded; only a total outage (every source failed) exits
non-zero, so cron/systemd alerts on that.

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
  landing.py   raw landing zone: gzip exact feed bytes before parsing (deduped)
  sources/     per-country feeds (the code that differs by country)
    base.py      Source Protocol (fetch/parse) + shared RSS parsing
    __init__.py  country -> sources registry; sources_for(country)
    us/          United States
      fda.py       FdaSource (FDA Recalls RSS)
      fsis.py      FsisSource (USDA FSIS meat/poultry/egg recalls RSS)
      __init__.py  SOURCES = [FdaSource(), FsisSource()]
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

Each poll first **lands the raw feed** (gzipped, byte-for-byte) under
`_landing/<country>/<source>/` before parsing — deduped by content hash so an
unchanged window isn't re-stored. This matters because the feed is a rolling
window you can't re-fetch: landing the raw lets us replay/re-parse history if the
parser improves or had a bug, and is an audit trail of what each feed said.

### Fetching: why FSIS isn't fetched like FDA

Both feeds are the same RSS shape and share one parser (`base.parse_rss`), so the
*parsing* is identical — only the HTTP fetch differs, and only for FSIS:

- **FDA** ([`us/fda.py`](recalls/sources/us/fda.py)) is a plain `httpx.get`. It
  serves the feed to any client; nothing special is needed.
- **FSIS** ([`us/fsis.py`](recalls/sources/us/fsis.py)) sits behind **Akamai Bot
  Manager**, which returns `403` based on the caller's **TLS/HTTP-2 fingerprint**,
  not its `User-Agent`. A plain `httpx`/`requests` call is blocked no matter what
  UA string it sends — but the *same URL loads fine in a real browser*. Proof:
  every `httpx` attempt (default UA, spoofed Chrome UA, browser `Accept` headers)
  returned `403` from the same machine whose Chrome opened the feed without issue.

  So `FsisSource.fetch` uses [`curl_cffi`](https://github.com/lexiforest/curl_cffi)
  with `impersonate="chrome"`, which replays Chrome's actual TLS handshake. That
  is the *whole* fix — it's a fingerprint problem, not geography, IP reputation, or
  auth (switching to FSIS's JSON API wouldn't help: it's behind the same Akamai
  host and 403s the same way). We deliberately **don't** apply `curl_cffi` to FDA:
  FDA doesn't need it, and keeping the lighter `httpx` path there makes the reason
  for the heavier client on FSIS explicit rather than blanket policy. If FSIS
  starts 403-ing again, bump the impersonation target to a newer Chrome; a fetch
  failure is logged and skipped, so it never blocks the FDA feed
  (see `poll.py` per-source isolation). Full details: [`docs/data-sources.md`](docs/data-sources.md#fsis--usda-recalls--public-health-alerts).

A run is scoped to one **country**: it polls that country's sources and writes
to its own database, `_data/<country>.db` (e.g. `_data/us.db`) — gitignored. All
three commands (`poll`/`list`/`history`) **require** `--country`, so a run never
silently targets the wrong per-country db; `poll` additionally requires
`--source`. (`RECALLS_COUNTRY` still sets the default for programmatic
`Config.from_env` use, but the CLI always makes you pass the flag.)

### Adding a country

The store, dedupe, history, and CLI are country-agnostic — only the feed differs.
`sources/ca/` is a ready-made skeleton (Canada). To add a country `<cc>`:

1. In `sources/<cc>/`, implement a `Source` (see `us/fda.py` for the pattern;
   reuse `sources/base.parse_rss` if the feed is RSS) and export it from the
   package's `SOURCES` list.
2. Register it in `sources/__init__.py`'s `_REGISTRY` (`"<cc>": <cc>.SOURCES`).
3. Document the feed in [`docs/data-sources.md`](docs/data-sources.md).

Then `uv run python -m recalls poll --country <cc> --source all` writes
`_data/<cc>.db`. No changes to the store, poll loop, or CLI.
