"""Backfill team boxscores into the lake (one ESPN summary fetch per game).

Resumable (only games missing boxscores), polite (per-game sleep), fail-soft.
Enables the Four Factors analytic. Usage:
  python scripts/run_dummy_sports_boxscore_backfill.py --league wnba [--limit N] [--min-interval 0.5]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.espn_boxscores import ingest_boxscores  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402

LEAGUES = ("wnba", "nba", "ncaamb", "nhl", "nfl")


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill lake boxscores.")
    ap.add_argument("--league", choices=LEAGUES, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-interval", type=float, default=0.5)
    args = ap.parse_args()

    store = SportsHistoryStore()
    try:
        res = ingest_boxscores(store, args.league, limit=args.limit, min_interval=args.min_interval)
        print(f"[{args.league}] {res}; boxscore rows in lake: {store.counts()['boxscores']}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
