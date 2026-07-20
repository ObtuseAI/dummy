"""Backfill the sports historical data lake from free public sources.

Read-only, polite (cached + rate-limited + backoff), resumable. Idempotent: a
re-run costs zero network (all cache hits) and creates no duplicate rows.

Usage:
  python scripts/run_dummy_sports_history_backfill.py                 # all sources, all seasons
  python scripts/run_dummy_sports_history_backfill.py --source nflverse --seasons 2020-2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.cfbfastr import ingest_cfbd_games  # noqa: E402
from autonomy.ingest.espn_lake import ingest_espn_league  # noqa: E402
from autonomy.ingest.wehoop import ingest_wehoop_wnba  # noqa: E402
from autonomy.ingest.fetcher import PoliteFetcher  # noqa: E402
from autonomy.ingest.nflverse import ingest_nflverse_games  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402

# Every league Dummy trades (ESPN scoreboard keys, lowercase).
ESPN_LEAGUES = ("mlb", "wnba", "nba", "nfl", "nhl", "ncaaf", "ncaamb")


def _ingest_espn(store, fetcher, seasons, only_league=None):  # noqa: ARG001
    from autonomy.sports.espn import EspnClient

    client = EspnClient()
    leagues = (only_league,) if only_league else ESPN_LEAGUES
    out = {}
    for league in leagues:
        out[league] = ingest_espn_league(store, client, league)
    return out


# source name -> ingest callable(store, fetcher, seasons)
SOURCES = {
    "nflverse": lambda store, fetcher, seasons: ingest_nflverse_games(store, fetcher, seasons=seasons),
    "cfbfastr": lambda store, fetcher, seasons: ingest_cfbd_games(store, fetcher, seasons=seasons),
    "wehoop": lambda store, fetcher, seasons: ingest_wehoop_wnba(store, fetcher, seasons or range(2008, 2027)),
    "espn": _ingest_espn,
}


def _parse_seasons(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",") if s.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill the sports history lake.")
    ap.add_argument("--source", choices=sorted(SOURCES) + ["all"], default="all")
    ap.add_argument("--seasons", default=None, help="e.g. 2020-2025 or 2023,2024")
    ap.add_argument("--league", default=None, choices=ESPN_LEAGUES,
                    help="restrict the espn source to one league (per-league scheduling)")
    ap.add_argument("--min-interval", type=float, default=1.5, help="per-host seconds between fetches")
    args = ap.parse_args()

    seasons = _parse_seasons(args.seasons)
    fetcher = PoliteFetcher(min_interval=args.min_interval)
    store = SportsHistoryStore()
    names = sorted(SOURCES) if args.source == "all" else [args.source]
    if args.league:                       # a single-league task only wants espn for that league
        names = [n for n in names if n == "espn"] or ["espn"]
    try:
        for name in names:
            if name == "espn":
                result = _ingest_espn(store, fetcher, seasons, only_league=args.league)
            else:
                result = SOURCES[name](store, fetcher, seasons)
            print(f"[{name}] {result}")
        print(f"lake counts: {store.counts()}  http: {fetcher.stats}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
