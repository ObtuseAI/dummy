"""Compile a strategy claim from text into a testable, falsifiability-graded spec.

    echo "Long BTC 4h breakout, enter on RSI<30, take profit +5%" \
        | python scripts/run_dummy_strategy_claim.py --source reddit

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

from autonomy.strategy_claim_compiler import compile_claim, record_claim  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--text", default=None, help="claim text (else read stdin)")
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args()

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
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
