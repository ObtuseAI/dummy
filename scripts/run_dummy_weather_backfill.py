"""Pre-train per-city weather forecast calibration from historical data.

Read-only: fetches past Open-Meteo forecasts vs ERA5 actuals, computes
per-city bias + sigma, writes runtime/autonomy/weather_calibration.json which
the weather signal auto-loads.

Usage:
    python scripts/run_dummy_weather_backfill.py [--kind HIGH|LOW] [--lookback-days N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.weather_calibration import run_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", default="HIGH", choices=("HIGH", "LOW"))
    parser.add_argument("--lookback-days", type=int, default=120)
    args = parser.parse_args()
    report = run_backfill(kind=args.kind, lookback_days=args.lookback_days)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["usable_count"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
