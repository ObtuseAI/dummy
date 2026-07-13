#!/usr/bin/env python
"""Propose-then-promote parameter tuner: nightly entrypoint (WS-9).

Read-only against the autonomy ledger. Fits each registered sigma/edge
scalar walk-forward against settled, market-benchmarked signal history and
writes the proposal artifact ``runtime/autonomy/tuning_proposals.json`` for
human review.

This is a proposer, not an actor: it has no session, execution, or capital
authority, and NEVER writes a constant back into any ``.py`` file. Promotion
of a proposal is an explicit, human-reviewed governance action -- a person
reads the artifact and edits the constant in a PR citing it.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.tuner import tuning_report, write_report  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
DEFAULT_OUT = Path("runtime/autonomy/tuning_proposals.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        report = tuning_report(conn, now_iso=datetime.now(timezone.utc).isoformat())
    finally:
        conn.close()
    write_report(report, args.out)
    print(json.dumps({
        "status": "OK",
        "settled_rows": report["settled_rows"],
        "tunables_evaluated": report["family_size"]["tunables_evaluated"],
        "grid_points_evaluated": report["family_size"]["grid_points_evaluated"],
        "candidates": report["candidate_count"],
        "out": str(args.out),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
