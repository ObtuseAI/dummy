"""Consolidated runner: one-command activation dry pipeline (V225 baseline -> V226 manifest pack -> V227 dry pipeline).

Dry by default. Contacts no broker, injects no adapter, writes no approval files, creates no runtime/approvals,
modifies no live-submit or caps. Fail-closed by construction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_v225_reports import main as gen_v225
from scripts.generate_v226_reports import main as gen_v226
from scripts.generate_v227_reports import main as gen_v227


def main() -> dict:
    v225 = gen_v225()
    v226 = gen_v226()
    v227 = gen_v227()
    return {
        "runner": "activation_pipeline",
        "verdict": v227.get("verdict"),
        "activation_pipeline_baseline_controller_status": v225.get("activation_pipeline_baseline_controller_status"),
        "manifest_pack_controller_status": v226.get("manifest_pack_controller_status"),
        "one_command_dry_pipeline_controller_status": v227.get("one_command_dry_pipeline_controller_status"),
        "broker_contacted": v227.get("real_broker_contacted", False),
        "firewall_submit_invoked": v227.get("firewall_submit_invoked", False),
        "approval_files_written": v227.get("approval_files_written", 0),
        "runtime_approvals_created_by_dummy": v227.get("runtime_approvals_created_by_dummy", False),
        "total_real_live_orders_submitted": v227.get("real_live_orders_submitted_count", 0),
        "current_next_action": v227.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
