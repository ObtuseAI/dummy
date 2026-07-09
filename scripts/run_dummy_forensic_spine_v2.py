"""Consolidated runner: forensic spine V2 (V221). Reviews hardened-live-proof forensics if a proof state exists. No new orders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_v221_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "forensic_spine_v2",
        "verdict": final.get("verdict"),
        "forensic_spine_v2_controller_status": final.get("forensic_spine_v2_controller_status"),
        "order_state": final.get("order_state"),
        "new_order_placed": final.get("new_order_placed", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
