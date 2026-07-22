"""Continuous shadow runner for the autonomy predator.

Default: one cycle per invocation (crash-isolated; run it from a scheduler).
--loop: internal loop on an interval (for foreground/background running).

Shadow-only by design: this daemon never trades real money. It accumulates
the settlement history the backtester and learner need. Honors the kill file.

Usage:
    python scripts/run_dummy_shadow_daemon.py               # one cycle
    python scripts/run_dummy_shadow_daemon.py --loop --interval 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _redirect_supervised_stdio() -> object | None:
    """Redirect Python and native child output before autonomy imports.

    ``WScript.Shell.Exec`` exposes bounded stdout/stderr pipes.  A supervisor
    that waits without draining them can deadlock if a dependency emits enough
    output.  The scheduled launcher supplies an absolute append-only log path;
    duplicating both OS descriptors also catches native-library writes that a
    simple ``sys.stdout`` replacement would miss.
    """
    raw_path = os.environ.get("DUMMY_SHADOW_STDIO_LOG", "").strip()
    if not raw_path:
        return None
    log_path = Path(raw_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(handle.fileno(), 1)
    os.dup2(handle.fileno(), 2)
    sys.stdout = handle
    sys.stderr = handle
    return handle


_SUPERVISED_LOG_HANDLE = _redirect_supervised_stdio()


from autonomy.daemon import run_one_cycle
from autonomy.executor import kill_switch_active
from autonomy.ontology import SessionMode
from autonomy.session import PAPER_RESULTS_AUTHORITY


def _retired_status() -> dict[str, object]:
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "status": PAPER_RESULTS_AUTHORITY,
        "mode": SessionMode.SHADOW.value,
        "orders_placed": 0,
        "signals_generated": 0,
        "settlements": 0,
        "execution_authority": False,
        "note": "Paper/shadow result production is retired; raw history remains audit-only.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="Run continuously instead of one cycle")
    parser.add_argument("--interval", type=float, default=300.0, help="Seconds between cycles in --loop mode")
    parser.add_argument("--max-cycles", type=int, default=0, help="Stop after N cycles (0 = unbounded)")
    args = parser.parse_args()

    if PAPER_RESULTS_AUTHORITY == "RETIRED_NON_AUTHORITATIVE":
        print(json.dumps(_retired_status(), indent=2, sort_keys=True))
        return 0

    if not args.loop:
        record = run_one_cycle(datetime.now(timezone.utc).isoformat(), SessionMode.SHADOW)
        print(json.dumps(record, indent=2, sort_keys=True, default=str))
        return 0

    cycles = 0
    while True:
        if kill_switch_active():
            print("kill switch active — daemon exiting")
            return 0
        record = run_one_cycle(datetime.now(timezone.utc).isoformat(), SessionMode.SHADOW)
        cycles += 1
        print(f"[{record.get('at')}] {record.get('status')} "
              f"orders={record.get('orders_placed')} signals={record.get('signals_generated')} "
              f"settlements={record.get('settlements')}")
        if args.max_cycles and cycles >= args.max_cycles:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
