"""Wave-42: refresh the dashboard snapshot artifact.

Builds ``runtime/autonomy/latest_dashboard_snapshot.json`` from the live ledger
so the web dashboard never opens the ledger itself. Default is a full refresh
(includes the backtest scan); ``--light`` reuses the last snapshot's backtest +
canary and refreshes only the cheap ledger summaries, so it can run frequently
without the minutes-long scan. A light run still forces a full backtest if the
prior one has aged past ``--backtest-max-age-hours`` (fail-fresh).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from autonomy.dashboard_snapshot import (
    build_dashboard_snapshot,
    read_dashboard_snapshot,
    write_dashboard_snapshot,
)
from autonomy.ledger import AutonomyLedger


def _backtest_age_hours(prior: dict | None) -> float | None:
    if not prior:
        return None
    try:
        ts = datetime.fromisoformat(str(prior.get("backtest_generated_at")))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh the dashboard snapshot artifact.")
    ap.add_argument("--light", action="store_true",
                    help="reuse the last backtest+canary; refresh only the summaries")
    # Safety-net only: in steady state the daemon's 6-hourly recalibration
    # refreshes the backtest in-process (no cross-process lock contention), so a
    # light run always sees a <6h backtest and stays cheap. This out-of-process
    # full backtest fires only when the daemon has NOT refreshed for 12h -- i.e.
    # it is down -- rather than racing the recal every 6h.
    ap.add_argument("--backtest-max-age-hours", type=float, default=12.0,
                    help="a light run runs a full backtest only if the prior one is older (daemon-down safety net)")
    args = ap.parse_args()

    prior = read_dashboard_snapshot()
    refresh_backtest = True
    if args.light:
        age = _backtest_age_hours(prior)
        # No prior backtest, or an unparseable/too-old one -> refresh it anyway.
        refresh_backtest = age is None or age > args.backtest_max_age_hours

    ledger = AutonomyLedger()
    try:
        snapshot = build_dashboard_snapshot(
            ledger, prior=prior, refresh_backtest=refresh_backtest,
        )
    finally:
        ledger.close()
    path = write_dashboard_snapshot(snapshot)
    print(f"wrote {path} (backtest_refreshed={refresh_backtest})")


if __name__ == "__main__":
    main()
