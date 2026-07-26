"""Consolidated runner: render the Dummy activation cockpit snapshot (read-only). No submit, no broker contact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.operator_status import build_activation_snapshot


def main() -> dict:
    snapshot = build_activation_snapshot()
    snapshot["generated_at"] = sgc.now_iso()
    snapshot["read_only"] = True
    snapshot["can_submit"] = False
    snapshot["can_write_approval_files"] = False
    sgc.write_report("activation_cockpit.json", snapshot)
    return snapshot


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
