"""Write a report-only OR-Tools portfolio challenger artifact."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.ledger import AutonomyLedger
from autonomy.portfolio_challenger import portfolio_challenger_from_ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--budget-cents", type=int, required=True)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--max-group-cost-cents", type=int)
    parser.add_argument("--max-group-positions", type=int, default=1)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("artifacts/dummy/portfolio_challengers"))
    args = parser.parse_args()
    ledger = AutonomyLedger(args.db)
    try:
        report = portfolio_challenger_from_ledger(
            ledger,
            budget_cents=args.budget_cents,
            max_positions=args.max_positions,
            max_group_cost_cents=args.max_group_cost_cents,
            max_group_positions=args.max_group_positions,
        )
    finally:
        ledger.close()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = args.out_dir / f"PORTFOLIO_CHALLENGER_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
