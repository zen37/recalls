"""The thin alert record.

Deliberately minimal: what a consumer needs to act (what, why, when, where to
read more) and a stable id to dedupe on. No severity/classification/lot modeling
-- that structured enrichment is the sibling data-platform's job, not this app's.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    guid: str          # stable id from the feed (RSS guid) -- the dedupe key
    title: str         # headline of the recall announcement
    link: str          # URL to the full official notice
    published: str     # ISO-8601 publish time (UTC), or "" if the feed omitted it
    summary: str       # description text from the feed
    source: str        # which feed it came from (e.g. "fda")
