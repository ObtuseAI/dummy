"""Consolidated runner: completion_lift_v5 (V254). Read-only / dry by default. No submit, no approval writes, no runtime/approvals, no broker contact by default."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.report_runtime import run_v254_reports as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "completion_lift_v5",
        "verdict": final.get("verdict"),
        "completion_lift_v5_controller_status": final.get("completion_lift_v5_controller_status"),
        "next_action_matrix_selection": final.get("next_action_matrix_selection"),
        "approval_files_written": final.get("approval_files_written", 0),
        "runtime_approvals_created_by_dummy": final.get("runtime_approvals_created_by_dummy", False),
        "real_broker_contacted": final.get("real_broker_contacted", False),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
