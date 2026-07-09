"""Read-only pre-submit validation for a proof candidate.

Validates the canonical V3 candidate (or an explicit ticker/price) against
live public Kalshi metadata. GET only; never POSTs, never arms anything.

Usage:
    python scripts/run_dummy_presubmit_validation.py [--ticker T --price P --count N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kalshi.presubmit import presubmit_validate, write_presubmit_report

V3_CANDIDATE_PATH = ROOT / "artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--price", type=int, default=None, help="Limit price in cents")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--side", default="yes", choices=("yes", "no"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    ticker, price, count, side = args.ticker, args.price, args.count, args.side
    if ticker is None:
        candidate = json.loads(V3_CANDIDATE_PATH.read_text(encoding="utf-8"))
        ticker = candidate["market_ticker"]
        price = price if price is not None else int(candidate.get("price", 1))
        count = int(candidate.get("count", count))
        side = candidate.get("side", side)
    elif price is None:
        parser.error("--price is required when --ticker is given")

    report = presubmit_validate(ticker=ticker, price_cents=price, count=count, side=side)
    payload = report.to_dict()
    if not args.no_write:
        payload["report_path"] = str(write_presubmit_report(report))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
