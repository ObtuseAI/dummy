#!/usr/bin/env python
"""Purge orphaned legacy trust keys from source_trust (Wave-5 P0-B).

The stale 2026-07 live branch wrote exact-scope trust rows with the OLD 3-part
grading key (``scope:crypto_spot_vol|ladder|hourly``); current code writes and
reads the 4-part ``scope:source|subject|market_type|horizon_or_phase`` key.
The legacy rows are orphaned — nothing updates them again — and twelve of them
froze at the 8.0 multiplicative cap, permanently tripping the auto-promotion
weight-saturation rail.

Default is a dry-run REPORT. ``--apply`` backs the doomed rows up to
``runtime/autonomy/trust_key_migration_backup.json`` and deletes them.
Bare-source and ``source@VERTICAL`` rows are never touched.

Usage:
    python scripts/migrate_trust_keys.py            # report only
    python scripts/migrate_trust_keys.py --apply    # backup + delete
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.auto_promotion_runner import _valid_trust_key  # noqa: E402

LEDGER_PATH = Path("runtime/autonomy/ledger.db")
BACKUP_PATH = Path("runtime/autonomy/trust_key_migration_backup.json")


def find_legacy_rows(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = []
    for source, weight, brier_sum, brier_count, updated_at in conn.execute(
        "SELECT source, weight, brier_sum, brier_count, updated_at FROM source_trust"
    ):
        if not _valid_trust_key(str(source)):
            rows.append({
                "source": source,
                "weight": weight,
                "brier_sum": brier_sum,
                "brier_count": brier_count,
                "updated_at": updated_at,
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="backup + delete legacy rows")
    parser.add_argument("--ledger", default=str(LEDGER_PATH), help="ledger.db path")
    args = parser.parse_args()

    ledger = Path(args.ledger)
    if not ledger.exists():
        print(f"ledger not found: {ledger}", file=sys.stderr)
        return 2

    mode = "rw" if args.apply else "ro"
    conn = sqlite3.connect(f"file:{ledger.resolve().as_posix()}?mode={mode}", uri=True)
    legacy = find_legacy_rows(conn)
    at_cap = [row for row in legacy if float(row["weight"]) >= 7.9999]
    print(f"legacy trust keys: {len(legacy)} (at 8.0 cap: {len(at_cap)})")
    for row in legacy:
        print(f"  {row['source']}  weight={row['weight']}")

    if not args.apply:
        print("dry-run: pass --apply to backup + delete")
        return 0
    if not legacy:
        print("nothing to migrate")
        return 0

    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    backup = {
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "reason": "orphaned 3-part scope keys from the stale 2026-07 branch",
        "rows": legacy,
    }
    BACKUP_PATH.write_text(json.dumps(backup, indent=2, sort_keys=True), encoding="utf-8")
    conn.executemany(
        "DELETE FROM source_trust WHERE source = ?",
        [(row["source"],) for row in legacy],
    )
    conn.commit()
    print(f"deleted {len(legacy)} rows; backup at {BACKUP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
