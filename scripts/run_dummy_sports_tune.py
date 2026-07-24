"""Self-tune each analytic's key parameter on the lake (edge-maximizing).

Point-in-time walk-forward grid search; writes runtime/autonomy/
sports_tuned_params.json, which the live signals load automatically. Usage:
  python scripts/run_dummy_sports_tune.py [--leagues nfl,wnba,mlb]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402
from autonomy.sports.tuner import tune_all  # noqa: E402

DEFAULT = ["nfl", "wnba", "mlb", "nba", "ncaamb", "ncaaf", "nhl"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Tune sports analytics on the lake.")
    ap.add_argument("--leagues", default=None, help="comma list; default all")
    # Sits under DummyTune's PT1H execution-time limit so the run ends on its
    # own terms and keeps its persisted progress, instead of being killed with
    # SCHED_S_TASK_TERMINATED. tune_all() orders least-recently-tuned first, so
    # whatever this budget cuts off is simply first in line on the next run.
    ap.add_argument(
        "--budget-s", type=float, default=float(os.environ.get("DUMMY_TUNE_BUDGET_S", 3000)),
        help="wall-clock budget in seconds; 0 disables",
    )
    args = ap.parse_args()
    leagues = args.leagues.split(",") if args.leagues else DEFAULT
    store = SportsHistoryStore()
    try:
        tuned = tune_all(store, leagues, budget_s=args.budget_s or None)
        for lg, params in tuned.items():
            for name, best in params.items():
                print(f"[{lg}] {name}: {best['param']}={best['value']} edge={best['edge']} (n={best['n']})")
        if not tuned:
            print("no leagues with enough graded history to tune yet")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
