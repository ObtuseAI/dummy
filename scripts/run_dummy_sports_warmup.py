"""Warm up per-league Elo ratings from the season's completed games (ESPN).

Read-only. Replays finals in chronological order into runtime/autonomy/elo_<league>.json.

Usage:
    python scripts/run_dummy_sports_warmup.py --league mlb --days-back 120
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.signals.sports_elo import SportsEloSignal  # noqa: E402


def _date_ranges(days_back: int, chunk: int = 10) -> list[str]:
    """Build ESPN YYYYMMDD-YYYYMMDD windows covering the trailing period."""
    today = datetime.now(timezone.utc).date()
    ranges: list[str] = []
    start = today - timedelta(days=days_back)
    while start < today:
        end = min(today, start + timedelta(days=chunk - 1))
        ranges.append(f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}")
        start = end + timedelta(days=1)
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--league", required=True,
        choices=("nba", "wnba", "nfl", "ncaaf", "mlb", "nhl", "ncaamb"),
    )
    parser.add_argument("--days-back", type=int, default=120)
    args = parser.parse_args()

    signal = SportsEloSignal()
    model = signal.warmup(args.league, _date_ranges(args.days_back))
    top = sorted(model.ratings.items(), key=lambda kv: kv[1], reverse=True)[:10]
    print(json.dumps({
        "league": args.league,
        "games_seen": model.games_seen,
        "teams_rated": len(model.ratings),
        "top_10": [{"team": t, "rating": round(r, 1)} for t, r in top],
    }, indent=2))
    return 0 if model.games_seen > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
