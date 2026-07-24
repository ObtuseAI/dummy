"""Compile a strategy claim from text into a testable, falsifiability-graded spec.

    echo "Long BTC 4h breakout, enter on RSI<30, take profit +5%" \
        | python scripts/run_dummy_strategy_claim.py --source reddit

MANUAL RESEARCH TOOL -- NOT WIRED INTO PRODUCTION (2026-07-24 audit, s6).
There is no scheduled task for this script and no automated backtest consumes
what it writes; a TESTABLE verdict means the claim COULD be tested, never that
it was tested. See ``autonomy/strategy_claim_compiler`` for why it was left
unwired rather than connected to the strategy miner.

Research spec only: it extracts, grades falsifiability, enumerates faithful
interpretations, and records the claim. It never trades.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.strategy_claim_compiler import (  # noqa: E402
    PIPELINE_STATUS,
    PIPELINE_STATUS_DETAIL,
    compile_claim,
    record_claim,
    registry_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--text", default=None, help="claim text (else read stdin)")
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument(
        "--status",
        action="store_true",
        help="print the claims-registry status and exit (no text needed)",
    )
    args = parser.parse_args()

    if args.status:
        print(json.dumps(registry_status(), indent=2, sort_keys=True))
        return 0

    text = args.text if args.text is not None else sys.stdin.read()
    if not text.strip():
        print(json.dumps({"status": "NO_TEXT"}))
        return 1
    compiled = compile_claim(text, source=args.source)
    if not args.no_record:
        record_claim(compiled)
    print(json.dumps({
        "status": "OK",
        "claim_id": compiled["claim"]["claim_id"],
        "verdict": compiled["falsifiability"]["verdict"],
        "unspecified_fields": compiled["claim"]["unspecified_fields"],
        "interpretation_count": compiled["interpretation_count"],
        # A TESTABLE verdict is not a test result: say so on every run.
        "pipeline_status": PIPELINE_STATUS,
        "pipeline_status_detail": PIPELINE_STATUS_DETAIL,
        "backtested": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
