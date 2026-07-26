"""Consolidated runner: hardened first-live-proof execution harness (V219).

Dry by default: this runner NEVER injects a firewall adapter or approval by itself. A live submit
requires BOTH env-gate variables set AND operator-supplied full authority (approval + adapter + caps +
live-submit already operator-enabled) AND a passing V218 arming check. Absent any of these it stays
fail-closed and submits nothing. This is the only live-proof fire surface in the V215-V224 bundle.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.report_runtime import run_v219_reports as generate_main


def main() -> dict:
    env_mode = os.environ.get("DUMMY_LIVE_PROOF_MODE", "") == "1"
    env_ack = os.environ.get("DUMMY_LIVE_PROOF_ACK", "")
    live_requested = env_mode and env_ack == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
    final = generate_main()
    return {
        "runner": "hardened_live_proof",
        "live_mode_requested": live_requested,
        "verdict": final.get("verdict"),
        "hardened_live_proof_execution_harness_controller_status": final.get("hardened_live_proof_execution_harness_controller_status"),
        "current_next_action": final.get("current_next_action"),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "real_broker_contacted": final.get("real_broker_contacted", False),
        "market_order_submitted": final.get("market_order_submitted", False),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
