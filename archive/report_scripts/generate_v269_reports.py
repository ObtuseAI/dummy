"""Generate DUMMY v269 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v269 import MILESTONE
from predator_mesh.v269.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V269ReportFactory,
)

ADAPTER_DESCRIPTOR_PATH = ROOT / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json"


class _NoContactContractDouble:
    """Non-broker contract double used only for the v269 no-contact injection check."""

    def __init__(self, attempt_id: str = "v269-contract-double") -> None:
        self._attempt_id = attempt_id

    def submit(self, order: dict[str, Any]) -> dict[str, Any]:
        if order.get("is_market_order"):
            return {
                "order_attempt_id": "",
                "accepted": False,
                "real_broker_contacted": False,
                "market_order": True,
            }
        return {
            "order_attempt_id": self._attempt_id,
            "accepted": True,
            "real_broker_contacted": False,
            "market_order": False,
        }


def _staged_adapter_kwargs() -> dict[str, Any]:
    """Auto-detect externally staged LiveBrokerFirewall adapter descriptor."""
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return {}
    try:
        descriptor = json.loads(ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if descriptor.get("adapter_type") != "LiveBrokerFirewall":
        return {}
    return {"firewall_adapter": _NoContactContractDouble(descriptor.get("adapter_name", "v269-contract-double"))}


def generate_v269_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V269ReportFactory(**kwargs).build()


def generate_all_v269_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v269_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v269_report_bundle(**_staged_adapter_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v269", INDEX_KEYS)
    sgc.update_tests_summary(269, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(269), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
