"""Consolidated runner: live-proof execute-once orchestrator (V230). Only fire surface in this bundle.

Dry by default: NEVER injects a firewall adapter or approval by itself. A live submit requires BOTH env-gate
variables AND operator-supplied full authority (approval + adapter + caps + live-submit already operator-enabled)
AND a passing V229 arming. Absent any of these it stays fail-closed and submits nothing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v230_reports import main as generate_main


def main() -> dict:
    env_mode = os.environ.get("DUMMY_LIVE_PROOF_MODE", "") == "1"
    env_ack = os.environ.get("DUMMY_LIVE_PROOF_ACK", "")
    live_requested = env_mode and env_ack == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
    final = generate_main()
    return {
        "runner": "live_proof_execute_once",
        "live_mode_requested": live_requested,
        "verdict": final.get("verdict"),
        "live_proof_execution_orchestrator_controller_status": final.get("live_proof_execution_orchestrator_controller_status"),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "real_broker_contacted": final.get("real_broker_contacted", False),
        "market_order_submitted": final.get("market_order_submitted", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
