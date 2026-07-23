"""Backfill referee tendencies from ESPN game summaries for one league.

Bounded, polite, resumable. Aggregates only (per-referee running totals);
research-only, no execution authority.

    python scripts/run_dummy_referee_backfill.py --league nba --max-games 300
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.referee_lake import backfill_referees  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True)
    parser.add_argument("--max-games", type=int, default=200)
    args = parser.parse_args()
    report = backfill_referees(
        SportsHistoryStore(), args.league, max_games=args.max_games,
    )
    report["status"] = "OK"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
