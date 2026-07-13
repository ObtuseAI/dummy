#!/usr/bin/env python
"""Nightly CLV grading pass (WS-8, spec section 3.2).

Read-only against the JSONL artifacts the mispricing monitor persists each
pass (``runtime/autonomy/paper_entries.jsonl`` / ``runtime/autonomy/
book_tape.jsonl``). Joins every persisted paper entry against its ticker's
book-tape close (the tape row nearest ``close_time`` within a 30-minute
window; nothing within the window means no grade -- fail-closed) and
aggregates the graded ``clv_bps`` per ``(specialist, market_type)`` with
per-event-cluster confidence intervals. Writes
``runtime/autonomy/clv_report.json`` for the dashboard.

CLV is EVIDENCE for review, never a promotion gate -- settlement-backed
contested Brier (autonomy/backtest.py, the nightly backtest schtask) remains
the sole promotion gate. This is a grader, not an actor: it has no session,
execution, or capital authority and changes no live parameter.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.clv import (  # noqa: E402
    DEFAULT_ENTRY_WINDOW_DAYS,
    build_clv_report,
    load_tape_rows,
)
from autonomy.strategy_miner import write_report  # noqa: E402

ENTRIES_PATH = Path("runtime/autonomy/paper_entries.jsonl")
TAPE_PATH = Path("runtime/autonomy/book_tape.jsonl")
OUT_PATH = Path("runtime/autonomy/clv_report.json")


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=ENTRIES_PATH)
    parser.add_argument("--tape", type=Path, default=TAPE_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument(
        "--window-days", type=float, default=DEFAULT_ENTRY_WINDOW_DAYS,
        help="only grade entries emitted within this trailing window "
             "(bounds the otherwise-cumulative nightly report)",
    )
    args = parser.parse_args()

    entries = _load_jsonl(args.entries)
    tape_rows = load_tape_rows(args.tape)
    report = build_clv_report(
        entries, tape_rows, now_iso=datetime.now(timezone.utc).isoformat(),
        window_days=args.window_days,
    )
    write_report(report, args.out)
    print(json.dumps({
        "status": "OK",
        "entries_total_seen": report["entries_total_seen"],
        "entries_in_window": report["entries_in_window"],
        "graded_entries": report["graded_entries"],
        "graded_event_clusters": report["graded_event_clusters"],
        "scopes": len(report["scopes"]),
        "out": str(args.out),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
