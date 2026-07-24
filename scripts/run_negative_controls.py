#!/usr/bin/env python
"""Run the negative-control battery against the live ledger (Wave-7).

Loads settled, market-benchmarked rows (the same rows readiness/promotion
grade on), runs the falsification battery per source, writes
``runtime/autonomy/negative_control_report.json`` and the NO_EDGE_MAP
(``runtime/autonomy/no_edge_map.json``) from the freshest backtest artifact.

Exit 0 = every powered source CLEAN. Exit 1 = at least one source flagged
(a NEGATIVE_CONTROL_FLAG alert is emitted; evidence-only, nothing is gated).

Cadence (2026-07-24 audit: "battery is CLEAN but ~40h stale while the backtest
runs ~3-hourly"): this runner is safe to fire on the BACKTEST cadence, not just
nightly. It is read-only, deterministic (fixed seed), bounded by the settled-row
scan, and self-skips when the report on disk is younger than
``MIN_RERUN_INTERVAL_HOURS`` — so the nightly chain and the scheduled task can
both call it without ever running the same battery twice in a row. A skipped run
still reports the standing verdict: a stale-but-FLAGGED report exits 1.
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.negative_controls import (  # noqa: E402
    MIN_CONTESTED_ROWS,
    REPORT_PATH,
    run_battery,
    write_report,
)
from autonomy.no_edge_map import build_no_edge_map, write_no_edge_map  # noqa: E402
from autonomy.strategy_miner import load_settled_rows  # noqa: E402

LEDGER_PATH = Path("runtime/autonomy/ledger.db")

# The controls grade the same settled rows the backtest does, so a control
# result older than a backtest refresh is stale evidence. Backtest cadence =
# 6h (``autonomy.daemon.RECAL_INTERVAL_HOURS`` / the DummyWeightsRecal task).
BACKTEST_CADENCE_HOURS = 6.0
# Half the cadence: the guard exists only to stop the scheduled task and the
# nightly chain re-running the same battery minutes apart. Sized UNDER the
# cadence on purpose — a guard equal to it would let clock jitter skip a whole
# period and silently halve the real cadence.
MIN_RERUN_INTERVAL_HOURS = BACKTEST_CADENCE_HOURS / 2.0


def _report_age_hours(now: datetime) -> tuple[float | None, dict]:
    """Age of the report on disk, or (None, {}) when there isn't a usable one."""
    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return None, {}
        generated_at = datetime.fromisoformat(str(report["generated_at"]))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None, {}
    if generated_at.tzinfo is None:  # naive stamp: treat as unusable, rerun
        return None, {}
    return (now - generated_at).total_seconds() / 3600.0, report


def main() -> int:
    now = datetime.now(timezone.utc)
    if "--force" not in sys.argv:
        age_hours, prior = _report_age_hours(now)
        if age_hours is not None and 0.0 <= age_hours < MIN_RERUN_INTERVAL_HOURS:
            flagged = list(prior.get("flagged_sources") or [])
            print(
                f"negative controls: {prior.get('status', 'UNKNOWN')} report is "
                f"{age_hours:.2f}h old (< {MIN_RERUN_INTERVAL_HOURS:.1f}h) -- skipping"
            )
            # Fail-closed: a fresh-but-FLAGGED verdict still exits nonzero.
            return 1 if flagged else 0

    conn = sqlite3.connect(f"file:{LEDGER_PATH.resolve().as_posix()}?mode=ro", uri=True)
    rows = load_settled_rows(conn)
    by_source: dict[str, list] = {}
    for row in rows:
        by_source.setdefault(row.source, []).append(row)
    powered = {s: r for s, r in by_source.items() if len(r) >= MIN_CONTESTED_ROWS}
    report = run_battery(powered)
    path = write_report(report)
    print(f"negative controls: {report['status']} "
          f"({report['powered_source_count']} powered / "
          f"{report['screened_source_count']} row-screened sources; "
          f"report {path})")
    for source in report["flagged_sources"]:
        flags = report["sources"][source]["flags"]
        print(f"  FLAGGED {source}: {', '.join(flags)}")
        try:
            from autonomy.alerts import emit_alert

            emit_alert(
                "NEGATIVE_CONTROL_FLAG",
                f"negative-control battery flagged {source}: {', '.join(flags)}",
                detail={"source": source, "flags": flags},
            )
        except Exception:
            pass

    # NO_EDGE_MAP from the freshest backtest artifact (best effort).
    artifacts = glob.glob("artifacts/dummy/backtests/AUTONOMY_BACKTEST_*.json")
    if artifacts:
        latest = max(artifacts, key=os.path.getmtime)
        backtest = json.loads(Path(latest).read_text(encoding="utf-8"))
        no_edge = build_no_edge_map(backtest)
        map_path = write_no_edge_map(no_edge)
        counts = no_edge["counts"]
        print(f"no-edge map: {counts} (artifact {map_path})")

    return 1 if report["flagged_sources"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
