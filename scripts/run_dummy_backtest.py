"""Offline backtest: score every signal source against settled markets.

Reads the autonomy ledger, grades each source's realized calibration, reports
realized decision P&L, and (with --bootstrap) writes derived trust weights
back so a live session starts pre-ranked. No network, no broker.

Usage:
    python scripts/run_dummy_backtest.py [--bootstrap] [--summary]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.adverse_selection import write_report as write_adverse_selection_report  # noqa: E402
from autonomy.backtest import (  # noqa: E402
    run_backtest,
    summarize_backtest,
    write_backtest_report,
    write_latest_backtest_summary,
)
from autonomy.ledger import AutonomyLedger  # noqa: E402

# Dedicated first-class adverse-selection artifact, produced alongside the
# backtest summary. Documented name so the readiness/governance review can cite
# it directly.
ADVERSE_SELECTION_ARTIFACT = Path("runtime/autonomy/adverse_selection.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="Write derived weights into the ledger")
    parser.add_argument("--no-write", action="store_true", help="Do not persist the report file")
    parser.add_argument("--summary", action="store_true", help="Print a compact decision-ready view")
    args = parser.parse_args()

    ledger = AutonomyLedger()
    try:
        report = run_backtest(ledger, bootstrap_weights=args.bootstrap)
        if not args.no_write and report.get("settled_markets", 0) > 0:
            report["report_path"] = str(write_backtest_report(report))
            # Emit the dedicated adverse-selection artifact alongside the
            # backtest summary (measurement only; no live behavior touched).
            adverse = report.get("execution_adverse_selection") or {}
            if adverse:
                write_adverse_selection_report(adverse, ADVERSE_SELECTION_ARTIFACT)
            # Refresh the authoritative freshness-stamped summary artifact so
            # downstream readiness/promotion evaluation never grades against
            # silently-aged evidence.
            write_latest_backtest_summary(summarize_backtest(report))
        print(json.dumps(
            summarize_backtest(report) if args.summary else report,
            indent=2, sort_keys=True,
        ))
    finally:
        ledger.close()
    return 0 if report.get("settled_markets", 0) > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
