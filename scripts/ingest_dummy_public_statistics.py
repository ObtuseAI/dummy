"""Ingest public raw statistics into Dummy's provenance ledger."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.ledger import AutonomyLedger
from autonomy.statistics_intake import collect_public_statistics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--out-dir", type=Path,
                        default=Path("artifacts/dummy/statistics_intake"))
    args = parser.parse_args()
    ledger = AutonomyLedger(args.db)
    try:
        report = collect_public_statistics(ledger)
    finally:
        ledger.close()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = args.out_dir / f"PUBLIC_STATISTICS_INTAKE_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
