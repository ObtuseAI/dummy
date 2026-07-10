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

from autonomy.backtest import run_backtest, write_backtest_report  # noqa: E402
from autonomy.ledger import AutonomyLedger  # noqa: E402


def _summary(report: dict) -> dict:
    policy = report.get("decision_policy") or {}
    ensemble = policy.get("ensemble_metrics") or {}
    walk_forward = (
        policy.get("walk_forward_threshold_selection") or {}
    ).get("aggregate_out_of_sample") or {}
    return {
        "report_name": report.get("report_name"),
        "report_path": report.get("report_path"),
        "created_at": report.get("created_at"),
        "settled_markets": report.get("settled_markets"),
        "decision_policy": {
            "settled_markets": policy.get("settled_markets", 0),
            "event_clusters": policy.get("event_clusters", 0),
            "forecast_brier": ensemble.get("forecast_brier"),
            "market_brier": ensemble.get("market_brier"),
            "brier_skill_vs_market": ensemble.get("brier_skill_vs_market"),
            "expected_calibration_error": ensemble.get("expected_calibration_error"),
            "cluster_robust_advantage": policy.get("cluster_robust_advantage", {}),
            "walk_forward_out_of_sample": walk_forward,
            "online_forecast_drift": policy.get("online_forecast_drift", {}),
        },
        "signal_data_quality": report.get("signal_data_quality", {}),
        "execution_quality_by_book": report.get("execution_quality_by_book", {}),
        "execution_drift_by_book": report.get("execution_drift_by_book", {}),
        "realized_trade_statistics": report.get("realized_trade_statistics", {}),
        "fill_conditioned_decision_policy": report.get(
            "fill_conditioned_decision_policy", {}
        ),
        "shadow_ttl_sensitivity": report.get("shadow_ttl_sensitivity", {}),
        "crypto_diagnostics": report.get("crypto_diagnostics", {}),
        "crypto_challenger_gates": report.get("crypto_challenger_gates", {}),
        "weights_written": report.get("weights_written", False),
    }


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
        print(json.dumps(_summary(report) if args.summary else report, indent=2, sort_keys=True))
    finally:
        ledger.close()
    return 0 if report.get("settled_markets", 0) > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
