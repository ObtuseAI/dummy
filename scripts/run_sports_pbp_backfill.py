"""Backfill the play-by-play knowledge lake for one league.

Bounded by design: one league per invocation, an explicit season list (or
--last N), polite fetch pacing, streamed parsing, aggregates only on disk.

    python scripts/run_sports_pbp_backfill.py --league wnba --last 5
    python scripts/run_sports_pbp_backfill.py --league nba --seasons 2021 2022 2023
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.pbp_lake import (  # noqa: E402
    PBP_SOURCES,
    ingest_pbp_seasons,
)

# Latest season currently published per source repo (checked 2026-07-22);
# --last counts back from here. Refresh when the repos advance.
LATEST_PUBLISHED_SEASON = {"wnba": 2022, "nba": 2023, "ncaamb": 2023, "nfl": 2025}
MAX_SEASONS_PER_RUN = 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True, choices=sorted(PBP_SOURCES))
    parser.add_argument("--seasons", type=int, nargs="*", default=None)
    parser.add_argument(
        "--last", type=int, default=None,
        help="Ingest the N most recent published seasons for the league.",
    )
    args = parser.parse_args()

    if args.seasons:
        seasons = sorted(set(args.seasons))
    elif args.last:
        newest = LATEST_PUBLISHED_SEASON[args.league]
        seasons = list(range(newest - max(1, args.last) + 1, newest + 1))
    else:
        newest = LATEST_PUBLISHED_SEASON[args.league]
        seasons = list(range(newest - 4, newest + 1))
    if len(seasons) > MAX_SEASONS_PER_RUN:
        print(json.dumps({
            "status": "REFUSED_TOO_MANY_SEASONS",
            "requested": len(seasons),
            "max_per_run": MAX_SEASONS_PER_RUN,
        }))
        return 1

    report = ingest_pbp_seasons(args.league, seasons)
    report["status"] = "OK" if report.get("ok") else "ERROR"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
