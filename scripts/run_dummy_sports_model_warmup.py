"""Warm all multi-sport challenger models from chronological completed events."""
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
from autonomy.signals.sports_intelligence import (  # noqa: E402
    BaseballIntelligenceSignal,
    TeamSportsIntelligenceSignal,
)


def _date_ranges(days_back: int, chunk_days: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days_back)
    ranges = []
    while start <= today:
        end = min(today, start + timedelta(days=chunk_days - 1))
        ranges.append(f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}")
        start = end + timedelta(days=1)
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days-back", type=int, default=365)
    parser.add_argument("--chunk-days", type=int, default=10)
    args = parser.parse_args()
    ranges = _date_ranges(max(30, args.days_back), max(1, args.chunk_days))
    report = {
        "public_read_only": True,
        "execution_authority": False,
        "capital_authority": False,
        "date_ranges": len(ranges),
        "models": {},
        "errors": [],
    }

    baseball = BaseballIntelligenceSignal()
    try:
        report["models"]["mlb_runs"] = {
            "new_games": baseball.warmup(ranges),
            "games_seen": baseball.model.games_seen,
        }
    except Exception as exc:
        report["errors"].append(f"mlb_runs:{type(exc).__name__}")

    team = TeamSportsIntelligenceSignal()
    elo = SportsEloSignal()
    for league in ("nba", "ncaamb", "nfl", "ncaaf", "nhl"):
        try:
            new_games = team.warmup(league, ranges)
            elo_model = elo.warmup(league, ranges)
            report["models"][league] = {
                "new_score_games": new_games,
                "score_games_seen": team.models[league].games_seen,
                "elo_games_seen": elo_model.games_seen,
            }
        except Exception as exc:
            report["errors"].append(f"{league}:{type(exc).__name__}")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
