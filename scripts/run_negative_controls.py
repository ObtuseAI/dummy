#!/usr/bin/env python
"""Run the negative-control battery against the live ledger (Wave-7).

Loads settled, market-benchmarked rows (the same rows readiness/promotion
grade on), runs the falsification battery per source, writes
``runtime/autonomy/negative_control_report.json`` and the NO_EDGE_MAP
(``runtime/autonomy/no_edge_map.json``) from the freshest backtest artifact.

Exit 0 = every powered source CLEAN. Exit 1 = at least one source flagged
(a NEGATIVE_CONTROL_FLAG alert is emitted; evidence-only, nothing is gated).
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.negative_controls import (  # noqa: E402
    MIN_CONTESTED_ROWS,
    run_battery,
    write_report,
)
from autonomy.no_edge_map import build_no_edge_map, write_no_edge_map  # noqa: E402
from autonomy.strategy_miner import load_settled_rows  # noqa: E402

LEDGER_PATH = Path("runtime/autonomy/ledger.db")


def main() -> int:
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
