#!/usr/bin/env python
"""Write the read-only, settlement-backed shadow exit-policy report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.exit_policy_evaluator import (  # noqa: E402
    exit_policy_report,
    open_read_only_ledger,
)


DEFAULT_LEDGER = Path("runtime/autonomy/ledger.db")
DEFAULT_OUT = Path("runtime/autonomy/exit_policy_evaluation.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    connection = open_read_only_ledger(args.db)
    try:
        report = exit_policy_report(connection)
    finally:
        connection.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(args.out)
    print(json.dumps({
        "status": report["status"],
        "eligible_decisions": report["eligible_decisions"],
        "passing_research_candidates": report["passing_research_candidates"],
        "live_sell_authorized": report["live_sell_authorized"],
        "out": str(args.out),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
