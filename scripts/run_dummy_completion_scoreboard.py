"""Consolidated runner: compute the Dummy completion scoreboard. No submit, no broker contact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v213.reports import build_scoreboard


def main() -> dict:
    scoreboard = build_scoreboard()
    scoreboard["generated_at"] = sgc.now_iso()
    scoreboard["live_orders"] = 0
    scoreboard["real_broker_contacted"] = False
    sgc.write_report("completion_scoreboard_v213.json", scoreboard)
    return scoreboard


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
