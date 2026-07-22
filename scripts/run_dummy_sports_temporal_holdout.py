"""Emit a fail-closed, research-only sports temporal holdout artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.temporal_holdout import run_temporal_holdout_gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-db", type=Path,
                        default=Path("runtime/autonomy/sports_history.db"))
    parser.add_argument("--league", required=True,
                        choices=("mlb", "nfl", "nba", "wnba", "nhl", "ncaaf", "ncaamb"))
    parser.add_argument("--holdout-season", required=True, type=int)
    parser.add_argument(
        "--confirm-completed-season", action="store_true",
        help="Required explicit confirmation that the requested league-season is complete.",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if not args.confirm_completed_season:
        parser.error("--confirm-completed-season is required; completion is never inferred")
    output = args.out or Path(
        f"runtime/autonomy/sports_temporal_holdout_{args.league}_{args.holdout_season}.json"
    )
    store = SportsHistoryStore(args.history_db)
    try:
        report = run_temporal_holdout_gate(
            store, league=args.league, holdout_season=args.holdout_season,
            artifact_path=output, confirm_completed_season=True,
            bootstrap_samples=args.bootstrap_samples, seed=args.seed,
        )
    finally:
        store.close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
