"""Consolidated runner: run the full first-live-proof path in DRY mode (V217).

Guarantees no broker contact, no broker payload, no LiveBrokerFirewall.submit, no account access, and no
writes to approval/config/caps. Uses the real resolver logic in dry mode only. Fail-closed by construction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v217_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "zero_broker_dry_validation",
        "verdict": final.get("verdict"),
        "zero_broker_dry_validation_controller_status": final.get("zero_broker_dry_validation_controller_status"),
        "current_next_action": final.get("current_next_action"),
        "broker_contacted": final.get("real_broker_contacted", False),
        "firewall_submit_invoked": final.get("firewall_submit_invoked", False),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
