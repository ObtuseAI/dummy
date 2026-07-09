"""Consolidated runner: execute-once final harness V4 (V261). Only fire surface in this bundle.

Dry by default: NEVER injects a firewall adapter or approval by itself. A live submit requires BOTH env-gate
variables AND operator-supplied full authority (approval + adapter + caps + live-submit already operator-enabled)
AND a passing V260 freeze. Absent any of these it stays fail-closed and submits nothing. Hard max one attempt,
auto-lock after attempt, no repeat submit, no direct broker bypass, no market order.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_v261_reports import main as generate_main


def main() -> dict:
    env_mode = os.environ.get("DUMMY_LIVE_PROOF_MODE", "") == "1"
    env_ack = os.environ.get("DUMMY_LIVE_PROOF_ACK", "")
    live_requested = env_mode and env_ack == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
    final = generate_main()
    return {
        "runner": "live_proof_execute_once_v4",
        "live_mode_requested": live_requested,
        "verdict": final.get("verdict"),
        "execute_once_final_harness_controller_status": final.get("execute_once_final_harness_controller_status"),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "real_broker_contacted": final.get("real_broker_contacted", False),
        "market_order_submitted": final.get("market_order_submitted", False),
        "approval_files_written": final.get("approval_files_written", 0),
        "runtime_approvals_created_by_dummy": final.get("runtime_approvals_created_by_dummy", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
