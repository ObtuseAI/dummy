"""Wave-44: the heavy backtest DIAGNOSTICS, split out of the 6-hourly recal.

The 6h recalibration (_maybe_recalibrate) now refreshes weights only and skips
the ~11 full-ledger-scan diagnostic sub-reports, so it stays fast and does not
block the next cycle. This task runs the FULL backtest on a lower cadence and
writes the artifacts the dashboard / readiness / promotion surfaces read: the
authoritative summary, the self-improvement plan, and the dashboard snapshot.
Weights are NOT re-persisted here (bootstrap_weights=False) -- that is the 6h
core's job.
"""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.backtest import (
    run_backtest,
    summarize_backtest,
    write_latest_backtest_summary,
)
from autonomy.ledger import AutonomyLedger


def main() -> None:
    now = datetime.now(timezone.utc)
    ledger = AutonomyLedger()
    try:
        report = run_backtest(ledger, bootstrap_weights=False, include_diagnostics=True)
        # Compute provenance once in the scheduled heavy-report window.  Live
        # canary preflight consumes this cached value and never scans the full
        # signal-history union view synchronously.
        report["evidence_split"] = ledger.evidence_split()
        report["bootstrapped_weights"] = ledger.all_weights()
        write_latest_backtest_summary(summarize_backtest(report))
        try:
            from autonomy.self_improvement import write_self_improvement_artifacts

            write_self_improvement_artifacts(report)
        except Exception:
            pass
        try:
            from autonomy.dashboard_snapshot import (
                build_dashboard_snapshot,
                write_dashboard_snapshot,
            )

            write_dashboard_snapshot(build_dashboard_snapshot(ledger, report=report, now=now))
        except Exception:
            pass
    finally:
        ledger.close()
    print(f"backtest report: settled={report.get('settled_markets')} "
          f"diagnostics={report.get('diagnostics_included')}")


if __name__ == "__main__":
    main()
