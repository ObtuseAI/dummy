"""Wave-46: prune redundant signal re-pricings for old-settled markets.

The ledger holds ~53 signals per settled market, but the backtester (and every
calibration/picks consumer) selects exactly ONE per (source, market): the
earliest opinion for a phantom market, or the latest opinion at/before the first
decision for a traded one (see ledger.calibration_signals_for_market). The other
intra-market re-pricings are redundant for scoring -- they are the ledger's bulk
(~70% of the settled rows) and slow every full scan.

This deletes, for markets settled more than ``settled_before_days`` ago (so the
market is certainly done being decided), every signal EXCEPT the one the
backtester selects per (source, market). It NEVER touches unsettled/pending
markets or recently-settled ones. Because the kept id is exactly the selected id,
the source weights are unchanged -- proven by test (weights identical
before/after) and, live, by the caller re-running the backtest around the prune.

Default is a dry run. Applying is gated so a bulk delete is a deliberate,
reviewed step.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import time
from typing import Any

from autonomy.ledger import AutonomyLedger
from autonomy.maintenance import (
    MaintenanceLease,
    acquire_maintenance,
    release_maintenance,
    retry_sqlite_locked,
)


def plan_prune(ledger: AutonomyLedger, settled_before_days: float = 7.0) -> dict[str, Any]:
    """Compute prunable ids without crossing point-in-time evidence lanes.

    Keep-selection mirrors calibration_signals_for_market independently for
    live and retro. Live rows must satisfy both model-time and durable
    receipt-time cutoffs; retro rows satisfy model time only. Unknown provenance
    is protected from deletion.
    """
    conn = ledger._conn
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settled_before_days)).isoformat()
    old_settled_count = int(conn.execute(
        "SELECT COUNT(*) FROM settlements WHERE settled_at < ?", (cutoff,)
    ).fetchone()[0])
    if old_settled_count == 0:
        return {
            "old_settled_markets": 0, "kept": 0, "prunable_ids": [],
            "prunable": 0, "total_scanned": 0,
        }

    # (market, source, provenance lane) -> selected id. Keeping lanes distinct
    # is essential: a later retro replay may never replace live evidence.
    keep: dict[tuple[str, str, str], int] = {}
    protected_unknown = 0
    prunable: list[int] = []
    total = 0
    for mt, sid, source, mode, decision_time, created_ok, receipt_ok in conn.execute(
        """
        WITH earliest_decision AS (
            SELECT market_ticker, MIN(created_at) AS decision_time
            FROM decisions GROUP BY market_ticker
        )
        SELECT sig.market_ticker, sig.id, sig.source, sig.mode,
               ed.decision_time,
               CASE
                   WHEN julianday(sig.created_at) <=
                        julianday(COALESCE(ed.decision_time, st.settled_at))
                   THEN 1 ELSE 0
               END AS created_in_window,
               CASE
                   WHEN sig.mode = 'retro' THEN 1
                   WHEN sig.mode = 'live'
                        AND julianday(sig.ingested_at) <=
                            julianday(COALESCE(ed.decision_time, st.settled_at))
                   THEN 1 ELSE 0
               END AS receipt_in_window
        FROM signals sig
        JOIN settlements st ON st.market_ticker = sig.market_ticker
        LEFT JOIN earliest_decision ed ON ed.market_ticker = sig.market_ticker
        WHERE st.settled_at < ?
        ORDER BY sig.id
        """,
        (cutoff,),
    ):
        total += 1
        mt = str(mt)
        lane = str(mode)
        sid = int(sid)
        if lane not in {"live", "retro"}:
            # Fail closed on destructive maintenance for unknown provenance.
            protected_unknown += 1
            continue
        key = (mt, str(source), lane)
        if not bool(created_ok) or not bool(receipt_ok):
            prunable.append(sid)
            continue
        selected_before = keep.get(key)
        if decision_time is None:
            if selected_before is None:
                keep[key] = sid  # earliest eligible phantom opinion
            else:
                prunable.append(sid)
        else:
            if selected_before is not None:
                prunable.append(selected_before)
            keep[key] = sid  # latest eligible opinion at/before decision

    prunable.sort()
    return {
        "old_settled_markets": old_settled_count,
        "kept": len(keep) + protected_unknown,
        "prunable_ids": prunable,
        "prunable": len(prunable),
        "total_scanned": total,
    }


def apply_prune(
    ledger: AutonomyLedger,
    prunable_ids: list[int],
    batch: int = 100_000,
    *,
    maintenance_wait_s: float | None = None,
    sqlite_lock_budget_s: float | None = None,
) -> int:
    """Delete the given signal ids. Returns rows deleted.

    Stages the ids into a temp table (temp_store=MEMORY) and issues ONE
    DELETE ... WHERE id IN (temp) under a single commit -- one lock acquisition
    that the busy-timeout rides out, instead of dozens of per-batch commits each
    racing the live cycle's writes (which is what made the batched version fail
    with 'database is locked' under contention).
    """
    conn = ledger._conn
    if not prunable_ids:
        return 0
    try:
        default_budget = float(os.environ.get("DUMMY_PRUNE_LOCK_BUDGET_S", "300"))
    except (TypeError, ValueError):
        default_budget = 300.0
    lock_budget = (
        max(0.01, default_budget)
        if sqlite_lock_budget_s is None
        else max(0.01, float(sqlite_lock_budget_s))
    )
    lease: MaintenanceLease | None = acquire_maintenance(
        ledger.db_path,
        "signal_prune",
        wait_seconds=maintenance_wait_s,
    )
    try:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS _prune_ids(id INTEGER PRIMARY KEY)")
        conn.execute("DELETE FROM _prune_ids")
        for i in range(0, len(prunable_ids), batch):
            conn.executemany(
                "INSERT OR IGNORE INTO _prune_ids(id) VALUES (?)",
                [(x,) for x in prunable_ids[i:i + batch]],
            )
        # End the temp-table staging transaction before explicitly acquiring
        # SQLite's one WAL writer lock.
        conn.commit()

        deleted = 0

        def _delete_transaction() -> None:
            nonlocal deleted
            if conn.in_transaction:
                conn.rollback()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.execute(
                    "DELETE FROM signals WHERE id IN (SELECT id FROM _prune_ids)"
                )
                deleted = int(cur.rowcount)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        retry_sqlite_locked(
            _delete_transaction,
            deadline_monotonic=time.monotonic() + lock_budget,
        )
        return deleted
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS _prune_ids")
        finally:
            release_maintenance(lease)
