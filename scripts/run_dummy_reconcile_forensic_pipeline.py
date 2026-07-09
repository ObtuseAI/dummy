"""Consolidated runner: reconcile + forensic auto pipeline (V231). Classifies + reviews proof if one exists. No new orders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_v231_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "reconcile_forensic_pipeline",
        "verdict": final.get("verdict"),
        "reconcile_forensic_pipeline_controller_status": final.get("reconcile_forensic_pipeline_controller_status"),
        "order_state": final.get("order_state"),
        "new_order_placed": final.get("new_order_placed", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
