# scripts/mlb_validation_report.py
"""Print the three-head validation scorecard for each MLB engine in the ledger.

Read-only. Establishes the current model's baseline: expect beat_close to be
unproven (the current baseball.py model is at market parity), which is the
harness telling the truth. Not a pytest test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.mlb_validation import score_engine, scorecard_to_dict  # noqa: E402
from autonomy.sports.simulation import SportsEvidenceLedger  # noqa: E402

RUNTIME = Path("runtime/autonomy/sports_simulation.db")


def main() -> int:
    if not RUNTIME.exists():
        print(f"No sports ledger at {RUNTIME}")
        return 0
    ledger = SportsEvidenceLedger(RUNTIME)
    try:
        rows = [r for r in ledger.rows(earliest_per_ticker_source=False)
                if r.sport == "mlb"]
        pnl_by_id: dict[str, int] = {}
        for d in ledger.recent_paper_decisions(status="SETTLED", limit=100000):
            if d.get("sport") == "mlb" and d.get("observation_id") and d.get("pnl_cents") is not None:
                pnl_by_id[str(d["observation_id"])] = int(d["pnl_cents"])
        sources = sorted({r.source for r in rows})
    finally:
        ledger.close()
    if not sources:
        print("No MLB engine decisions in the ledger yet.")
        return 0
    for source in sources:
        card = score_engine(rows, pnl_by_id, source)
        print(json.dumps(scorecard_to_dict(card), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
