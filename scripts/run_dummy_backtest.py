"""Offline backtest: score every signal source against settled markets.

Reads the autonomy ledger, grades each source's realized calibration, reports
realized decision P&L, and (with --bootstrap) writes derived trust weights
back so a live session starts pre-ranked. No network, no broker.

Usage:
    python scripts/run_dummy_backtest.py [--bootstrap]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.backtest import run_backtest, write_backtest_report
from autonomy.ledger import AutonomyLedger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="Write derived weights into the ledger")
    parser.add_argument("--no-write", action="store_true", help="Do not persist the report file")
    args = parser.parse_args()

    ledger = AutonomyLedger()
    try:
        report = run_backtest(ledger, bootstrap_weights=args.bootstrap)
        if not args.no_write and report.get("settled_markets", 0) > 0:
            report["report_path"] = str(write_backtest_report(report))
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        ledger.close()
    return 0 if report.get("settled_markets", 0) > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
