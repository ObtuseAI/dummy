"""Ops watchdog runner: one aggregate health pass over the scheduled fleet.

Usage:
    python scripts/run_dummy_watchdog.py [--runtime-dir DIR] [--quiet]

Reads each known task's freshest artifact under runtime/autonomy, compares age
vs 2x that task's cadence, checks cycle-error streaks / ledger size / kill-file
/ free-disk floor, writes runtime/autonomy/watchdog_status.json, and fires
de-duplicated operator alerts. Read-only over the runtime tree -- it never
opens ledger.db and never controls a scheduled task. Crash-isolated and
scheduler-friendly: one pass per invocation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.watchdog import RUNTIME_DIR, run_watchdog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", default=str(RUNTIME_DIR))
    parser.add_argument("--ledger-max-gb", type=float, default=None)
    parser.add_argument("--disk-floor-gb", type=float, default=None)
    parser.add_argument("--no-alerts", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    kwargs = {}
    if args.ledger_max_gb is not None:
        kwargs["ledger_max_gb"] = args.ledger_max_gb
    if args.disk_floor_gb is not None:
        kwargs["disk_floor_gb"] = args.disk_floor_gb

    status = run_watchdog(
        Path(args.runtime_dir),
        emit_alerts=not args.no_alerts,
        **kwargs,
    )
    if not args.quiet:
        print(json.dumps(status, indent=2, sort_keys=True))
    # Exit non-zero when unhealthy so a supervisor/last-result surface notices.
    return 0 if status.get("healthy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
