"""Consolidated runner: reconcile spine V2 (V220). Classifies hardened-live-proof state if one exists. No new orders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v220_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "reconcile_spine_v2",
        "verdict": final.get("verdict"),
        "reconcile_spine_v2_controller_status": final.get("reconcile_spine_v2_controller_status"),
        "order_state": final.get("order_state"),
        "new_order_placed": final.get("new_order_placed", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
