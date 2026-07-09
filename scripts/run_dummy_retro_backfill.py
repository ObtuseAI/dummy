"""Run the retro evidence backfill: grade point-in-time forecasts against
markets that already settled, then (optionally) bootstrap trust weights.

Usage:
  python scripts/run_dummy_retro_backfill.py                     # default windows
  python scripts/run_dummy_retro_backfill.py --crypto-days 14 --weather-days 30
  python scripts/run_dummy_retro_backfill.py --bootstrap         # + weights + gate report
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.ledger import AutonomyLedger  # noqa: E402
from autonomy.retro import RetroEvidenceEngine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Dummy retro evidence backfill")
    parser.add_argument("--crypto-days", type=float, default=10.0)
    parser.add_argument("--weather-days", type=float, default=30.0)
    parser.add_argument("--crypto-max", type=int, default=250, help="max settled markets per crypto series")
    parser.add_argument("--weather-max", type=int, default=60, help="max settled markets per weather series")
    parser.add_argument("--bootstrap", action="store_true",
                        help="after backfill, derive+write trust weights and print the canary gate")
    args = parser.parse_args()

    ledger = AutonomyLedger()
    try:
        engine = RetroEvidenceEngine(ledger)
        report = engine.run(
            crypto_days=args.crypto_days,
            weather_days=args.weather_days,
            crypto_max_per_series=args.crypto_max,
            weather_max_per_series=args.weather_max,
        )
        print(json.dumps(report, indent=2, sort_keys=True))

        if args.bootstrap:
            from autonomy.backtest import run_backtest, write_backtest_report
            from autonomy.canary import evaluate_canary_readiness

            backtest = run_backtest(ledger, bootstrap_weights=True)
            path = write_backtest_report(backtest)
            print(f"\nbacktest report: {path}")
            summary = {s: {k: v[k] for k in ("n", "mean_brier", "beat_market_rate")}
                       for s, v in backtest.get("sources", {}).items()}
            print(json.dumps({"settled_markets": backtest.get("settled_markets"),
                              "sources": summary,
                              "derived_weights": backtest.get("derived_weights")},
                             indent=2, sort_keys=True))
            readiness = evaluate_canary_readiness(ledger)
            print("\nCANARY GATE:")
            print(json.dumps(readiness.to_dict(), indent=2, sort_keys=True))
    finally:
        ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
