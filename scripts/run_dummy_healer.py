#!/usr/bin/env python
"""Self-heal / reconnect pass (Wave-33). One crash-isolated fire: probe the
data venues for connectivity and restart any continuously-running task that
has died. Writes runtime/autonomy/heal_status.json for the dashboard.

Never controls capital and never touches ledger.db; it only queries and
restarts the fleet's own scheduled tasks. Fail-open throughout.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Windowless launch (pythonw): stdio handles are None; keep prints alive.
if sys.stdout is None or sys.stderr is None:
    _log_dir = ROOT / "runtime" / "autonomy"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _stream = open(_log_dir / "healer_stdout.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _stream
    sys.stderr = sys.stderr or _stream

STATUS_PATH = ROOT / "runtime" / "autonomy" / "heal_status.json"
_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _query_states() -> dict[str, str]:
    """{taskName: state} for every Dummy* task, via Get-ScheduledTask."""
    out = subprocess.run(
        _PS + ["Get-ScheduledTask -TaskName 'Dummy*' | "
               "Select-Object TaskName,State | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=60)
    data = json.loads(out.stdout or "[]")
    if isinstance(data, dict):
        data = [data]
    states: dict[str, str] = {}
    for row in data:
        name = str(row.get("TaskName"))
        state = row.get("State")
        # State serializes as an int enum or a name depending on host; map both.
        states[name] = _STATE_NAMES.get(state, str(state))
    return states


# ScheduledTask State enum -> name (ConvertTo-Json may emit the int).
_STATE_NAMES = {3: "Ready", 4: "Running", 1: "Disabled", 2: "Queued",
                "Ready": "Ready", "Running": "Running", "Disabled": "Disabled",
                "Queued": "Queued"}


def _restart(name: str) -> bool:
    result = subprocess.run(
        _PS + [f"Start-ScheduledTask -TaskName '{name}'"],
        capture_output=True, text=True, timeout=60)
    return result.returncode == 0


def main() -> int:
    from autonomy.healer import assess

    now = datetime.now(timezone.utc).isoformat()
    report = assess(now_iso=now, query_states=_query_states, restart=_restart)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATUS_PATH)
    print(json.dumps(report.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
