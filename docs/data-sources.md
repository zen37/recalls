# Data Sources

Catalog of the official recall feeds this app ingests, one section per country.
This app is the **near-real-time alerts** product, so every source here is chosen
for *timeliness* — same-day announcements consumers can act on — not for
structured/historical completeness (that is the sibling
[`recalls-os`](https://github.com/zen37/recalls-os) data platform's job).

Each source records: the feed, its format, what it covers, how fresh it is, how
we identify records, auth, and the known limits we design around.

---

## United States

### FDA — Recalls, Market Withdrawals & Safety Alerts (lead source)

The FDA's public announcement feed: firm-issued recall notices published as they
happen, before the FDA's slower classification/enforcement process.

| | |
|---|---|
| **Feed (RSS)** | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml` |
| **Human page** | https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts |
| **Format** | RSS 2.0 (XML) |
| **Auth** | None |
| **Freshness** | Same day — items appear as firms/FDA post announcements |
| **Coverage** | FDA-regulated products: **foods** (produce, dairy, packaged/processed, seafood, shell eggs), **drugs**, **cosmetics**, dietary supplements, some devices, and pet food |
| **Record identity** | RSS `<guid>` (`isPermaLink="true"`) = the announcement URL. We dedupe on this. |
| **Config** | `RECALLS_FEED_URL` (defaults to the URL above) |

**Item fields we map** (`feed.py` → `Alert`):

| RSS element | Alert field | Notes |
|---|---|---|
| `guid` | `guid` | stable id / dedupe key; equals the link for this feed |
| `title` | `title` | headline of the recall |
| `link` | `link` | URL to the full official notice |
| `pubDate` | `published` | RFC-822 → normalized to ISO-8601 UTC |
| `description` | `summary` | free-text summary (firm, product, reason) |

**Known limits we design around:**

- **Rolling window (~20 items).** The feed holds only the most recent
  announcements; older ones scroll off. We miss a recall only if *more than a
  full window* is published between two polls, so poll frequently (15 min /
  hourly). The `possible_gap` warning (`poll.py`) fires if a poll finds an
  all-new window against a non-empty store — the signal we fell behind. See the
  README "Polling cadence" section.
- **Not a historical archive.** First poll captures only what's in the window
  now; there is no backfill of past recalls here by design. Full history is
  `recalls-os`'s paged-API job.
- **Thin, free-text content.** The RSS carries a summary, not structured fields
  (no parsed lot codes, no Class I/II/III severity). Severity/lot enrichment
  comes weeks later from the FDA enforcement dataset — out of scope for this
  timely product.
- **Updates in place.** A revised notice keeps the same guid; we detect content
  changes via a hash and record them in `alerts_history` (see README).

### FSIS — USDA Recalls & Public Health Alerts

The USDA Food Safety and Inspection Service feed, covering the products the FDA
does *not*: **meat, poultry, and processed egg products**. A different agency
with its own same-day feed, so it is a second US source, not a replacement for
FDA. Its RSS is shaped exactly like the FDA feed, so parsing reuses the same
`parse_rss` (no FSIS-specific parser).

| | |
|---|---|
| **Feed (RSS)** | `https://www.fsis.usda.gov/fsis-content/rss/recalls.xml` |
| **Human page** | https://www.fsis.usda.gov/recalls |
| **Format** | RSS 2.0 (XML) |
| **Auth** | None, but bot-protected — must be fetched with a browser TLS fingerprint (see limits) |
| **Freshness** | Same day — recalls and public health alerts as FSIS posts them |
| **Coverage** | FSIS-regulated products: **meat, poultry, processed egg products**; includes both recalls (Class I–III) and public health alerts |
| **Record identity** | RSS `<guid>` (`isPermaLink="true"`) = the announcement URL. We dedupe on this. |
| **Config** | None — FSIS always uses its own feed. The single `RECALLS_FEED_URL` override applies only to FDA (honoring it here would point both US feeds at the same URL). |

**Item fields we map** (same mapping as FDA, via `base.parse_rss` → `Alert`):

| RSS element | Alert field | Notes |
|---|---|---|
| `guid` | `guid` | stable id / dedupe key; equals the link for this feed |
| `title` | `title` | headline of the recall / public health alert |
| `link` | `link` | URL to the full official notice (`/recalls-alerts/...`) |
| `pubDate` | `published` | RFC-822 (`+0000`) → normalized to ISO-8601 UTC |
| `description` | `summary` | CDATA HTML (leading icon `<img>` + free-text summary) |

**Known limits we design around:**

- **Bot/CDN filtering.** The feed sits behind Akamai Bot Manager, which returns
  `403` based on the client's **TLS/HTTP-2 fingerprint**, not its `User-Agent` —
  a plain `httpx`/`requests` call is blocked no matter what UA it sends, while a
  real browser loads the same URL fine. So `FsisSource.fetch` uses
  [`curl_cffi`](https://github.com/lexiforest/curl_cffi) with `impersonate="chrome"`,
  which replays Chrome's actual TLS handshake. (FDA needs none of this and stays
  on `httpx`.) If FSIS starts 403-ing again, bump the impersonation target to a
  newer Chrome. A source failing this way is logged and skipped, so it never
  blocks the FDA feed (see `poll.py` per-source isolation).
- **Both recalls and public health alerts.** Unlike FDA, the feed mixes firm
  recalls with FSIS-issued public health alerts (issued when a recall can't yet
  be recommended). Both are real, actionable consumer alerts, so we ingest both;
  we do not try to separate them (no severity/class modeling — that's `recalls-os`).
- **HTML in the summary.** `description` is CDATA HTML leading with an icon
  `<img>`; we store it verbatim (same as the feed gives it). Any stripping is a
  presentation concern for a future UI/notifier, not ingestion.
- **`"pha"` glued to some titles.** On *public health alert* items the feed's own
  `<title>` ends with a stray `pha` token (e.g. `...Contaminationpha`) — an
  upstream category tag leaking into the title, not a parse bug. We store the
  title verbatim; stripping a trailing `pha` is an optional source-specific
  cleanup left for a presentation layer.
- **Rolling window & "updates in place"** behave like FDA (see above): a revised
  notice keeps its guid; content changes are caught by hash and recorded in
  `alerts_history`.

---

## Canada

_Placeholder — not yet implemented._

| | |
|---|---|
| **Candidate source** | Canada Recalls / Recalls and Safety Alerts (Health Canada + CFIA food recalls) |
| **Feed** | TBD |
| **Format** | TBD |
| **Auth** | TBD |
| **Coverage** | TBD |
| **Record identity** | TBD |
| **Known limits** | TBD |

---

## United Kingdom

_Placeholder — not yet implemented._

| | |
|---|---|
| **Candidate source** | FSA (Food Standards Agency) food alerts |
| **Feed** | TBD |
| **Format** | TBD |
| **Auth** | TBD |
| **Coverage** | TBD |
| **Record identity** | TBD |
| **Known limits** | TBD |

---

## Germany

_Placeholder — not yet implemented._

| | |
|---|---|
| **Candidate source** | Lebensmittelwarnung.de (food/product warnings) |
| **Feed** | TBD |
| **Format** | TBD |
| **Auth** | TBD |
| **Coverage** | TBD |
| **Record identity** | TBD |
| **Known limits** | TBD (source prunes expired records) |

---

## France

_Placeholder — not yet implemented._

| | |
|---|---|
| **Candidate source** | RappelConso (official product recalls) |
| **Feed** | TBD |
| **Format** | TBD |
| **Auth** | TBD |
| **Coverage** | TBD |
| **Record identity** | TBD |
| **Known limits** | TBD |

---

> When implementing a country: fill in its section above (feed, format, coverage,
> identity, limits), then write a connector that maps its items into the same
> `Alert` shape. The store, dedupe, and history layers are source-agnostic — a
> new source is a new `source` value + a feed parser, not a schema change.
