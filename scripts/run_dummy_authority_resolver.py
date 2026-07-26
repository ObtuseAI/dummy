"""Consolidated runner: resolve Dummy dry/live authority state (single source of truth). No submit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.operator_status import resolve_authority


def main() -> dict:
    resolved = resolve_authority()
    resolved["generated_at"] = sgc.now_iso()
    resolved["live_orders"] = 0
    resolved["real_broker_contacted"] = False
    sgc.write_report("authority_resolver.json", resolved)
    return resolved


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
