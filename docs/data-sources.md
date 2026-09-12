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

**Deliberately *not* in scope (US):**

- **USDA FSIS** (meat, poultry, processed egg products) — a *different agency*
  with its own fast recall feed. Not covered here yet; our current scope is
  FDA-regulated foods. A candidate future source (see below).

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
