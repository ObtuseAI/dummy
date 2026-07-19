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
from typing import Any

from autonomy.ledger import AutonomyLedger


def plan_prune(ledger: AutonomyLedger, settled_before_days: float = 7.0) -> dict[str, Any]:
    """Compute the prunable signal ids without deleting anything.

    Returns counts + the sorted prunable id list. Keep-selection mirrors
    ledger.calibration_signals_for_market EXACTLY (min id for phantom, max id
    with created_at<=first-decision for traded), so deleting the rest cannot move
    a weight.
    """
    conn = ledger._conn
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settled_before_days)).isoformat()
    old_settled = {str(r[0]) for r in conn.execute(
        "SELECT market_ticker FROM settlements WHERE settled_at < ?", (cutoff,))}
    if not old_settled:
        return {"old_settled_markets": 0, "kept": 0, "prunable_ids": [], "prunable": 0, "total_scanned": 0}

    decision_times: dict[str, str] = {}
    for mt, dt in conn.execute("SELECT market_ticker, MIN(created_at) FROM decisions GROUP BY market_ticker"):
        if dt is not None and str(mt) in old_settled:
            decision_times[str(mt)] = str(dt)

    keep: dict[tuple[str, str], int] = {}   # (market, source) -> selected id
    prunable: list[int] = []
    total = 0
    # id is the PK, so ORDER BY id is index-ordered (no sort). Ascending order
    # makes "first seen" == min id (phantom) and "last qualifying" == max id (traded).
    for mt, sid, source, ca in conn.execute(
        "SELECT market_ticker, id, source, created_at FROM signals ORDER BY id"
    ):
        mt = str(mt)
        if mt not in old_settled:
            continue
        total += 1
        key = (mt, str(source))
        dt = decision_times.get(mt)
        selected_before = keep.get(key)
        if dt is None:
            if selected_before is None:
                keep[key] = int(sid)        # earliest phantom opinion
            else:
                prunable.append(int(sid))
        else:
            if ca is not None and str(ca) <= dt:
                if selected_before is not None:
                    prunable.append(selected_before)  # older in-window loses to this later one
                keep[key] = int(sid)         # latest opinion at/before the decision
            else:
                prunable.append(int(sid))    # after the decision -> never selected
    prunable.sort()
    return {
        "old_settled_markets": len(old_settled),
        "kept": len(keep),
        "prunable_ids": prunable,
        "prunable": len(prunable),
        "total_scanned": total,
    }


def apply_prune(ledger: AutonomyLedger, prunable_ids: list[int], batch: int = 100_000) -> int:
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
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _prune_ids(id INTEGER PRIMARY KEY)")
    conn.execute("DELETE FROM _prune_ids")
    for i in range(0, len(prunable_ids), batch):
        conn.executemany(
            "INSERT OR IGNORE INTO _prune_ids(id) VALUES (?)",
            [(x,) for x in prunable_ids[i:i + batch]],
        )
    cur = conn.execute("DELETE FROM signals WHERE id IN (SELECT id FROM _prune_ids)")
    deleted = int(cur.rowcount)
    ledger._retry_on_locked(conn.commit)  # noqa: SLF001 - trusted ledger consumer
    conn.execute("DROP TABLE IF EXISTS _prune_ids")
    return deleted
