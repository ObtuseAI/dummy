"""Run one supervised, public-read-only forecast grading pass."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.grading_worker import (  # noqa: E402
    DEFAULT_MIN_ATTEMPT_COVERAGE,
    DEFAULT_RECEIPT_PATH,
    run_grading_pass,
)
from autonomy.ledger import AutonomyLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("runtime/autonomy/ledger.db"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_RECEIPT_PATH,
    )
    parser.add_argument("--lookback-hours", type=float, default=24.0 * 7.0)
    parser.add_argument("--max-pages-per-series", type=int, default=20)
    parser.add_argument(
        "--minimum-attempt-coverage",
        type=float,
        default=DEFAULT_MIN_ATTEMPT_COVERAGE,
    )
    args = parser.parse_args()

    ledger = AutonomyLedger(args.ledger)
    try:
        result = run_grading_pass(
            ledger,
            receipt_path=args.receipt,
            lookback_hours=args.lookback_hours,
            max_pages_per_series=args.max_pages_per_series,
            minimum_attempt_coverage=args.minimum_attempt_coverage,
        )
    finally:
        ledger.close()
    print(json.dumps(result.receipt, indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
