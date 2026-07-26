"""Backfill player-level boxscores for a basketball league from ESPN summaries.

Bounded, polite, resumable (games without player rows are re-fetched cheaply).
Feeds the player-prop projection model. Research-only, no execution authority.

    python scripts/run_dummy_player_boxscore_backfill.py --league nba --limit 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.sports.boxscores import fetch_summary, parse_player_boxscores  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True, choices=["nba", "wnba", "ncaamb"])
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--min-interval", type=float, default=1.0)
    args = parser.parse_args()

    store = SportsHistoryStore()
    game_ids = store.game_ids_missing_boxscores(args.league, limit=args.limit)
    games = rows = errors = 0
    for i, gid in enumerate(game_ids):
        try:
            summary = fetch_summary(args.league, gid)
            observed_at = datetime.now(timezone.utc).isoformat()
            player_rows = parse_player_boxscores(args.league, summary)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if player_rows:
            rows += store.record_player_boxscores(
                [
                    {
                        **row,
                        "source_available_at": observed_at,
                        "received_at": observed_at,
                        "source": "espn",
                    }
                    for row in player_rows
                ]
            )
            games += 1
        if args.min_interval and i < len(game_ids) - 1:
            time.sleep(args.min_interval)
    print(json.dumps({
        "status": "OK", "league": args.league,
        "games_with_players": games, "player_rows": rows, "errors": errors,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
