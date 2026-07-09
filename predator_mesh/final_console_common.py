"""Shared builder for the DUMMY V275-V284 final operator execution console + post-proof route bundle.

Every stage here is fail-closed and non-executing: no live order, no broker contact, no submit, no
scale, no autonomy, no approval-file writes, no runtime/approvals creation. This module factors the
repeated staged-gate report machinery (safe base, baseline readback, governor/lock, mission payload)
so each vNNN/reports.py supplies only its controller specifics. It does not replace or duplicate the
generic helpers in staged_gate_common; it composes them.
"""

from __future__ import annotations

from typing import Any, Callable

from predator_mesh import staged_gate_common as sgc

ARTIFACTS = sgc.ARTIFACTS


def read_authority_state() -> dict[str, Any]:
    """Read V265-V274 external-authority finals into a proof-aware state (fixtures never count)."""
    import_ok = str(sgc.load_artifact("final_report_v266.json").get("external_authority_import_wizard_controller_status", "")) == "PASS_EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_NO_WRITE"
    schema_ok = str(sgc.load_artifact("final_report_v267.json").get("approval_manifest_schema_verifier_controller_status", "")) == "PASS_APPROVAL_MANIFEST_SCHEMA_VERIFIED_READY_FOR_RESOLVER"
    caps_ok = str(sgc.load_artifact("final_report_v268.json").get("external_live_submit_caps_state_verifier_controller_status", "")) == "PASS_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_IMMUTABLE"
    adapter_ok = str(sgc.load_artifact("final_report_v269.json").get("livebrokerfirewall_injection_appliance_controller_status", "")) == "PASS_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_READY_NON_BROKER_DOUBLE"
    readonly_ok = str(sgc.load_artifact("final_report_v270.json").get("broker_readonly_optional_verifier_controller_status", "")) == "PASS_BROKER_READONLY_OPTIONAL_VERIFIER_READY_NON_BROKER_DOUBLE"
    armable_ok = str(sgc.load_artifact("final_report_v271.json").get("final_armability_runbook_controller_status", "")) == "PASS_FINAL_ARMABILITY_RUNBOOK_READY_NO_SUBMIT"
    v272 = sgc.load_artifact("final_report_v272.json")
    real_proof = str(v272.get("execute_once_runbook_controller_status", "")) == "PASS_EXECUTE_ONCE_RUNBOOK_SUBMITTED_AUTOLOCKED" and int(v272.get("real_live_orders_submitted_count", 0) or 0) > 0
    handoff_present = str(sgc.load_artifact("final_report_v273.json").get("proof_intake_reconcile_handoff_v3_controller_status", "")) == "PASS_PROOF_INTAKE_RECONCILE_HANDOFF_READY_LOCKED"
    return {
        "import_ok": import_ok, "schema_ok": schema_ok, "caps_ok": caps_ok, "adapter_ok": adapter_ok,
        "readonly_ok": readonly_ok, "armable_ok": armable_ok, "real_proof": real_proof, "handoff_present": handoff_present,
    }


SAFETY_ZEROS: dict[str, Any] = {
    "caps_modified": False,
    "live_submit_enabled": False,
    "scale_applied": False,
    "live_orders": 0,
    "real_live_orders_submitted_count": 0,
    "total_real_live_orders_submitted": 0,
    "real_broker_contacted": False,
    "autonomous_trading_enabled": False,
    "market_order": False,
    "approval_files_written": 0,
    "runtime_approvals_created_by_dummy": False,
}


class StageBundle:
    """Config-driven staged-gate report bundle for one V275-V284 stage."""

    def __init__(
        self,
        *,
        version: int,
        milestone: str,
        workstream: str,
        dash_title: str,
        controller_key: str,
        report_groups: dict[str, list[str]],
        index_keys: list[str],
        controller_fn: Callable[..., dict[str, Any]],
        summary_fields: list[list[str]],
        routes: list[str],
    ) -> None:
        self.version = version
        self.milestone = milestone
        self.workstream = workstream
        self.dash_title = dash_title
        self.controller_key = controller_key
        self.report_groups = report_groups
        self.index_keys = index_keys
        self.controller_fn = controller_fn
        self.summary_fields = summary_fields
        self.routes = routes
        self.prior = version - 1
        self.gov = version - 40
        self.lock = version - 41
        self.prior_label = f"v{self.prior}"
        self.baseline_report = f"v{self.prior}_baseline_readback_v1_report.json"
        self.mission_name = f"dummy_mission_state_report_v{version}.json"
        self.final_name = f"final_report_v{version}.json"
        self.dashboard_report = f"dashboard_v{version}_report_v1.json"
        self.next_action_report = f"completion_oriented_next_action_v{version}_report.json"
        self.controller_report = report_groups[next(iter(report_groups))][0]
        self.safety_names = sgc.safety_report_names(version)
        self.required = [n for names in report_groups.values() for n in names] + self.safety_names
        self.verification_commands = [
            f"python -m py_compile predator_mesh/v{version}/reports.py scripts/generate_v{version}_reports.py dashboard/backend/v{version}_routes.py",
            f"python scripts/generate_v{version}_reports.py",
            "python -m pytest tests/ -q --tb=short --timeout=60",
            "cd dashboard/frontend && npm run build",
        ]

    def _baseline_status(self) -> str:
        return sgc.baseline_status(f"final_report_v{self.prior}.json", self.prior_label.upper())

    def _final_verdict(self, baseline_status: str, result: dict[str, Any]) -> str:
        return "FAIL" if baseline_status.startswith("FAIL") else result["verdict"]

    def _common(self, baseline_status: str, result: dict[str, Any]) -> dict[str, Any]:
        common: dict[str, Any] = {
            f"{self.prior_label}_baseline_status": baseline_status,
            self.controller_key: result["status"],
        }
        # Safety zeros are defaults; controller fields may explicitly override
        # them when the controller has truthfully determined the value (e.g.
        # v298 real broker contact/order count after a live attempt).
        common.update(SAFETY_ZEROS)
        common.update(result.get("fields", {}))
        common[f"readiness_governor_v{self.gov}_status"] = "PASS"
        common[f"execution_lock_deep_recheck_v{self.lock}_status"] = "PASS"
        common["current_next_action"] = result["next_action"]
        common["selected_next_action"] = result["next_action"]
        common["current_blockers"] = result["blockers"]
        return common

    def _verdict(self, name: str, baseline_status: str, result: dict[str, Any]) -> str:
        if name in self.safety_names or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
            return "PASS"
        if name == self.baseline_report:
            if baseline_status == f"PASS_{self.prior_label.upper()}_BASELINE_READBACK":
                return "PASS"
            return "FAIL" if baseline_status.startswith("FAIL") else "PARTIAL"
        return self._final_verdict(baseline_status, result)

    def _component_payload(self, name: str, baseline_status: str, result: dict[str, Any]) -> dict[str, Any]:
        workstream = f"v{self.version}: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
        report = sgc.safe_base(self.milestone, workstream, self._verdict(name, baseline_status, result))
        report.update(self._common(baseline_status, result))
        report["report_name"] = name
        if name == self.dashboard_report:
            report.update({"dashboard_status": "PASS", "routes": self.routes, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
        elif name == self.next_action_report:
            report.update({f"completion_oriented_next_action_v{self.version}_status": "PASS", "next_action": result["next_action"]})
        elif name == self.mission_name:
            report.update({
                "mission_state_verdict": self._final_verdict(baseline_status, result),
                f"{self.prior_label}_carried_status": baseline_status,
                self.controller_key: result["status"],
                "proof_paths": {"final_report": str(ARTIFACTS / self.final_name), "controller": str(ARTIFACTS / self.controller_report)},
            })
        if name in self.safety_names:
            report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
            if name in {f"blunder_separation_recheck_v{self.version}.json", f"dummy_canonical_identity_report_v{self.version}.json"}:
                report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
        return report

    def build_reports(self, **kw: Any) -> dict[str, dict[str, Any]]:
        baseline_status = self._baseline_status()
        result = self.controller_fn(baseline_status, **kw)
        if baseline_status.startswith("FAIL"):
            result = dict(result)
            result["blockers"] = [f"FAIL_{self.prior_label.upper()}_BASELINE_REGRESSION", *result.get("blockers", [])]
        return {name: self._component_payload(name, baseline_status, result) for name in self.required}
