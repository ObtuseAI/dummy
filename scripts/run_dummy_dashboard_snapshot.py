"""Wave-42: refresh the dashboard snapshot artifact.

Builds ``runtime/autonomy/latest_dashboard_snapshot.json`` from the live ledger
so the web dashboard never opens the ledger itself.

Two modes:
  * default -- full refresh (runs the backtest). This scans the whole ledger and
    holds a SHARED lock for the duration (~tens of minutes on a large ledger), so
    run it ONLY as a one-shot manual seed in a quiet window, never on a timer.
  * ``--light`` -- refresh only the cheap ledger summaries (~1-2s) and carry the
    prior snapshot's backtest + canary forward unchanged. This NEVER runs a full
    backtest out-of-process; that is exactly the contention Wave-42 removes. The
    full backtest belongs to the daemon's in-process 6-hourly recalibration,
    which never contends with the brain because it IS the brain's process.

So the recurring ``DummyDashboardSnapshot`` task uses ``--light`` and is always
cheap. Before the first recalibration seeds a backtest, ``--light`` writes a
snapshot whose backtest is empty; the scoreboard/canary panels fill in at the
next recal (or a manual full seed).
"""
from __future__ import annotations

import argparse

from autonomy.dashboard_snapshot import (
    build_dashboard_snapshot,
    read_dashboard_snapshot,
    write_dashboard_snapshot,
)
from autonomy.ledger import AutonomyLedger


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh the dashboard snapshot artifact.")
    ap.add_argument("--light", action="store_true",
                    help="refresh only the cheap summaries and carry the backtest forward; "
                         "never runs a full backtest out-of-process")
    args = ap.parse_args()

    prior = read_dashboard_snapshot()
    ledger = AutonomyLedger()
    try:
        snapshot = build_dashboard_snapshot(
            ledger, prior=prior, refresh_backtest=not args.light,
        )
    finally:
        ledger.close()
    path = write_dashboard_snapshot(snapshot)
    print(f"wrote {path} (backtest_refreshed={not args.light})")


if __name__ == "__main__":
    main()
