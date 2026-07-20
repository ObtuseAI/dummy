"""Backfill nflfastR play-by-play EPA into the lake (offense/defense per game).

Open data, no key. Resumable via record_team_boxscores upsert. Usage:
  python scripts/run_dummy_sports_epa_backfill.py --seasons 2016-2024
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.ingest.nflfastr import ingest_nflfastr_epa  # noqa: E402
from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402


def _seasons(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",") if s.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill nflfastR EPA.")
    ap.add_argument("--seasons", default="2020-2024", help="e.g. 2016-2024 or 2023,2024")
    args = ap.parse_args()
    store = SportsHistoryStore()
    try:
        res = ingest_nflfastr_epa(store, _seasons(args.seasons))
        print(f"nflfastR EPA: {res}; lake boxscores: {store.counts()['boxscores']}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
