"""Bounded ESPN date-range re-observation for one league's past seasons.

Re-observes historical scoreboard dates so finals ingest under the current
provenance rules: a final seen >48h after start gets the derived
source_reported bound (start + 12h), making retro seasons eligible for
strict point-in-time evaluation without fabricating observation times.

Polite by construction: one scoreboard call per date via the shared client,
optional date cap per run, resumable (dates already fully final+stamped in
the lake are skipped cheaply).

    python scripts/run_espn_date_range_backfill.py --league mlb \
        --start 2023-03-30 --end 2023-11-02
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.espn_lake import ingest_espn_league  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--max-dates", type=int, default=400)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()

    from autonomy.sports.espn import EspnClient

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        print(json.dumps({"status": "ERROR_BAD_RANGE"}))
        return 1

    store = SportsHistoryStore()
    client = EspnClient()
    processed = 0
    rows = 0
    finals = 0
    day = start
    while day <= end and processed < args.max_dates:
        stamp = day.strftime("%Y%m%d")
        result = ingest_espn_league(
            store, client, args.league, dates=stamp,
        )
        processed += 1
        rows += int(result.get("rows") or 0)
        finals += int(result.get("finals") or 0)
        day += timedelta(days=1)
        time.sleep(max(0.2, args.sleep_seconds))

    eligibility = store.evaluation_eligibility(league=args.league)
    store.close()
    print(json.dumps({
        "status": "OK" if day > end else "PARTIAL_DATE_CAP",
        "league": args.league,
        "dates_processed": processed,
        "rows": rows,
        "finals": finals,
        "resume_from": day.isoformat() if day <= end else None,
        "eligible_now": eligibility["eligible"],
        "rejection_reasons": eligibility["rejection_reasons"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
