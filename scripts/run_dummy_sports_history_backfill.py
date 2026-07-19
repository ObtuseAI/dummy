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

from autonomy.ingest.fetcher import PoliteFetcher  # noqa: E402
from autonomy.ingest.nflverse import ingest_nflverse_games  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402

# source name -> ingest callable(store, fetcher, seasons)
SOURCES = {
    "nflverse": lambda store, fetcher, seasons: ingest_nflverse_games(store, fetcher, seasons=seasons),
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
    ap.add_argument("--min-interval", type=float, default=1.5, help="per-host seconds between fetches")
    args = ap.parse_args()

    seasons = _parse_seasons(args.seasons)
    fetcher = PoliteFetcher(min_interval=args.min_interval)
    store = SportsHistoryStore()
    names = sorted(SOURCES) if args.source == "all" else [args.source]
    try:
        for name in names:
            result = SOURCES[name](store, fetcher, seasons)
            print(f"[{name}] {result}")
        print(f"lake counts: {store.counts()}  http: {fetcher.stats}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
