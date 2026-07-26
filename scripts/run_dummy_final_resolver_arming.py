"""Consolidated runner: final resolver + arming orchestrator (V229). No submit. Dry/blocked by default."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.report_runtime import run_v229_reports as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "final_resolver_arming",
        "verdict": final.get("verdict"),
        "final_resolver_arming_controller_status": final.get("final_resolver_arming_controller_status"),
        "arming_ready": final.get("arming_ready", False),
        "total_real_live_orders_submitted": final.get("real_live_orders_submitted_count", 0),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
