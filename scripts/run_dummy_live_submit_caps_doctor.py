"""Consolidated runner: live_submit_caps_doctor (V237). Read-only diagnostic. No submit, no approval writes, no runtime/approvals, no broker contact by default."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_v237_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "live_submit_caps_doctor",
        "verdict": final.get("verdict"),
        "live_submit_caps_doctor_controller_status": final.get("live_submit_caps_doctor_controller_status"),
        "failure_code": final.get("failure_code"),
        "approval_files_written": final.get("approval_files_written", 0),
        "runtime_approvals_created_by_dummy": final.get("runtime_approvals_created_by_dummy", False),
        "real_broker_contacted": final.get("real_broker_contacted", False),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
