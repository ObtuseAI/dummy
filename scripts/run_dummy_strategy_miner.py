#!/usr/bin/env python
"""Strategy-mining pass: reverse-engineer edges from settled signal history.

Read-only against the autonomy ledger. Mines walk-forward, market-benchmarked
rules from every recorded signal emission (taken AND missed) and writes the
proposal artifact ``runtime/autonomy/strategy_mining_report.json`` for review.

This is a proposer, not an actor: it has no session, execution, or capital
authority, changes no live parameter, and any adopted rule ships
challenger-only through the normal promotion gates.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.strategy_miner import mining_report, write_report  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
OUT_PATH = Path("runtime/autonomy/strategy_mining_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--sources", nargs="*", default=None,
        help="restrict mining to these signal sources (default: all non-prior)",
    )
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1
    now_iso = datetime.now(timezone.utc).isoformat()
    registry_status = "SKIPPED"
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        report = mining_report(
            conn,
            sources=tuple(args.sources) if args.sources else None,
            now_iso=now_iso,
        )
        # Wave-63: mined candidates auto-register for forward tracking so
        # out-of-sample evidence starts accruing the same day they are found.
        # Registration is disclosure, never adoption (fail-soft: a registry
        # problem must not cost the mining report).
        try:
            from autonomy.strategy_miner import (
                load_settled_rows,
                update_mined_rule_forward_registry,
            )

            rows = load_settled_rows(
                conn, sources=tuple(args.sources) if args.sources else None,
            )
            registry = update_mined_rule_forward_registry(
                rows, report, now_iso=now_iso,
            )
            registry_status = f"{len(registry.get('rules', {}))}_tracked"
        except Exception as exc:  # noqa: BLE001
            registry_status = f"ERROR:{type(exc).__name__}"
    finally:
        conn.close()
    write_report(report, OUT_PATH)
    print(json.dumps({
        "status": "OK",
        "settled_rows": report["settled_rows"],
        "rules": len(report["rules"]),
        "candidates": report["candidate_count"],
        "forward_registry": registry_status,
        "out": str(OUT_PATH),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
