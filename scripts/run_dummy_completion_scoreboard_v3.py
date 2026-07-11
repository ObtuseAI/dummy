"""Consolidated runner: completion scoreboard V3 (V233). Proof-aware completion percentages. No submit, no broker contact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v233_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "completion_scoreboard_v3",
        "verdict": final.get("verdict"),
        "completion_scoreboard_v3_controller_status": final.get("completion_scoreboard_v3_controller_status"),
        "fully_operational_estimate": final.get("fully_operational_estimate"),
        "first_live_proof_present": final.get("first_live_proof_present", False),
        "next_command_recommendation": final.get("next_command_recommendation"),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
