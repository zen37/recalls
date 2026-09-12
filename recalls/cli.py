"""CLI: ``python -m recalls <command>`` (or the ``recalls`` script).

Commands:
  poll            fetch the feed once, store new alerts, print what's new
  list [--limit]  show recent stored alerts
"""

from __future__ import annotations

import argparse
import difflib
import logging
import os
import sys

from .config import Config
from .landing import open_landing
from .poll import poll_once
from .sources import sources_for
from .store import open_store


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _cmd_poll(config: Config) -> int:
    store = open_store(config)
    landing = open_landing(config)
    result = poll_once(config, store, landing)
    print(
        f"fetched {result.fetched}, {len(result.new)} new, "
        f"{len(result.updated)} updated"
    )
    if result.possible_gap:
        print(
            "WARNING: every fetched item was new -- you may have fallen behind the "
            "feed window and missed older recalls. Poll more frequently."
        )
    return 0


def _cmd_list(config: Config, query: str | None, limit: int) -> int:
    store = open_store(config)
    alerts = store.find_alerts(query, limit) if query else store.recent(limit)
    if not alerts:
        if query:
            print(f"no alerts match {query!r}")
        else:
            print("no alerts stored yet -- run `python -m recalls poll` first")
        return 0
    for a in alerts:
        print(f"{a.published or '?':<25}  {'[' + a.source + ']':<8}  {a.title}")
        print(f"{'':<25}  {'':<8}  {a.link}")
    return 0


def _resolve_query_to_guid(store, query: str) -> str | None:
    """Resolve a guid substring to a single guid, or print guidance and return None."""
    matches = store.find_alerts(query)
    guids = list(dict.fromkeys(a.guid for a in matches))  # distinct, order-preserving
    if not guids:
        print(f"no alert matches {query!r}")
        return None
    if len(guids) > 1:
        print(f"{query!r} matches {len(guids)} alerts -- be more specific:")
        seen = set()
        for a in matches:
            if a.guid in seen:
                continue
            seen.add(a.guid)
            print(f"  {a.title}")
            print(f"    {a.guid}")
        return None
    return guids[0]


def _entry_fields(e) -> list[str]:
    """The comparable content of a history entry, one 'field: value' per line."""
    return [
        f"title:     {e.title}",
        f"published: {e.published}",
        f"link:      {e.link}",
        f"summary:   {e.summary}",
    ]


def _cmd_history(
    config: Config, query: str | None, event_id: int | None, limit: int, full: bool, diff: bool
) -> int:
    store = open_store(config)

    # Scope to a single alert by either a short history event id (--id) or a
    # substring of its guid/title (positional) -- so you never paste the full URL.
    guid: str | None = None
    if event_id is not None:
        guid = store.guid_of(event_id)
        if guid is None:
            print(f"no history event with id {event_id}")
            return 1
    elif query is not None:
        guid = _resolve_query_to_guid(store, query)
        if guid is None:
            return 1  # no match / ambiguous -- guidance already printed

    entries = store.history(guid=guid, limit=limit)
    if not entries:
        print("no history yet -- run `python -m recalls poll` first")
        return 0

    if diff:
        # Show what changed between consecutive versions. Diffing needs a single
        # alert's timeline in chronological order (store returns newest-first).
        if not guid:
            print("--diff needs a single alert: pass a guid substring or --id N. "
                  "Showing recent events; re-run scoped to one alert for field-level "
                  "changes.\n")
        chrono = list(reversed(entries))
        prev = None
        for e in chrono:
            print(f"[{e.history_id}] {e.changed_at}  {e.change_type.upper()}  [{e.source}]")
            if prev is None:
                for line in _entry_fields(e):
                    print(f"    {line}")
            else:
                delta = list(difflib.unified_diff(
                    _entry_fields(prev), _entry_fields(e),
                    lineterm="", n=0,
                ))
                changed = [d for d in delta if d and d[0] in "+-" and d[:2] not in ("--", "++")]
                if changed:
                    for d in changed:
                        print(f"    {d}")
                else:
                    print("    (no field difference recorded)")
            print()
            prev = e
        return 0

    for e in entries:
        print(f"[{e.history_id:>5}] {e.changed_at:<22} {e.change_type.upper():<8} "
              f"{'[' + e.source + ']':<8} {e.title}")
        print(f"{'':>8} {'':<22} {'':<8} {'':<8} {e.link}")
        if full:
            print(f"{'':>8} {'':<22} {'':<8} {'':<8} {e.summary}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    _configure_logging()

    parser = argparse.ArgumentParser(prog="recalls", description=__doc__)
    # Shared across subcommands: which country's sources/db to operate on.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--country",
        help="country to operate on (overrides RECALLS_COUNTRY; default 'us')",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("poll", parents=[common], help="fetch the feed once and store new alerts")
    p_list = sub.add_parser("list", parents=[common], help="show recent stored alerts")
    p_list.add_argument("query", nargs="?",
                        help="filter to alerts whose guid/title contains this substring")
    p_list.add_argument("--limit", type=int, default=20, help="how many to show")
    p_hist = sub.add_parser("history", parents=[common],
                            help="show change history (new/updated events)")
    p_hist.add_argument("query", nargs="?",
                        help="scope to one alert by a substring of its guid/title (URL)")
    p_hist.add_argument("--id", type=int, dest="event_id",
                        help="reference an alert by a history id from the listing "
                             "(shown in [brackets]) instead of pasting its URL")
    p_hist.add_argument("--limit", type=int, default=50, help="how many events to show")
    p_hist.add_argument("--full", action="store_true", help="also print each version's summary")
    p_hist.add_argument("--diff", action="store_true",
                        help="show field-level changes between versions (best with a guid/--id)")

    args = parser.parse_args(argv)
    config = Config.from_env(country=args.country)

    try:
        # Validate the country up front (before any DB file is created) so an
        # unsupported RECALLS_COUNTRY fails cleanly instead of leaving a stray db.
        sources_for(config.country)
        if args.command == "poll":
            return _cmd_poll(config)
        if args.command == "list":
            return _cmd_list(config, args.query, args.limit)
        if args.command == "history":
            return _cmd_history(
                config, args.query, args.event_id, args.limit, args.full, args.diff
            )
    except ValueError as exc:
        # e.g. unsupported country / store backend -- a config problem, not a bug.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
