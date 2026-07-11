"""Consolidated runner: run the approved first-live-proof path (V209). Dry by default; live requires exact CLI/env gate AND full authority. Fail-closed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v209_reports import main as generate_main


def main() -> dict:
    # Live mode requires BOTH the explicit env gate variables; absence => dry (no submit).
    env_mode = os.environ.get("DUMMY_LIVE_PROOF_MODE", "") == "1"
    env_ack = os.environ.get("DUMMY_LIVE_PROOF_ACK", "")
    live_requested = env_mode and env_ack == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
    # This runner NEVER injects a firewall adapter or approval by itself; without operator-supplied
    # authority the underlying stage stays fail-closed and submits nothing.
    final = generate_main()
    out = {
        "runner": "first_live_proof",
        "live_mode_requested": live_requested,
        "verdict": final.get("verdict"),
        "current_next_action": final.get("current_next_action"),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "real_broker_contacted": final.get("real_broker_contacted", False),
    }
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
