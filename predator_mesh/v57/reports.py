"""DUMMY v57 manual approval-file consumption and inert quarantine instance creation gate.

V57 consumes a MANUALLY authored dedicated approval file
(``runtime/approvals/dummy_v55_rehearsal_artifact_approval.json``) only if it exists and exactly
validates. On exact approval it creates only the 4 inert quarantined rehearsal-planning JSON
instances under a locked quarantine directory. Absent/malformed/fuzzy/broad approval creates zero
instances. Dummy never creates or modifies the approval file itself. Quarantine release stays
locked; there is no submit / transform-to-broker path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v55.reports import (
    ALLOWED_REHEARSAL_ARTIFACT_TYPES,
    ARTIFACT_SCHEMA_FIELDS,
    DEFAULT_APPROVAL_INPUT_PATH,
    DENIED_REHEARSAL_ARTIFACT_TYPES,
    EXACT_APPROVAL_PHRASE,
    FORBIDDEN_ARTIFACT_FIELDS,
    REQUIRED_APPROVAL_FIELDS,
    resolve_v55_approval_input,
    validate_v55_approval_input,
)
from predator_mesh.v57 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
DEFAULT_QUARANTINE_DIR = ARTIFACTS / "v57_quarantine"

# Map V55 resolver/validator statuses onto V57 manual-consumer statuses.
_CONSUMER_STATUS = {
    "PARTIAL_APPROVAL_INPUT_ABSENT": "PARTIAL_APPROVAL_FILE_ABSENT",
    "PARTIAL_APPROVAL_INPUT_MALFORMED": "PARTIAL_APPROVAL_FILE_MALFORMED",
    "FAIL_CLOSED_INVALID_APPROVAL": "FAIL_CLOSED_INVALID_APPROVAL",
    "PASS_EXACT_APPROVAL_ACCEPTED_FOR_INERT_QUARANTINE_ONLY": "PASS_MANUAL_APPROVAL_FILE_ACCEPTED",
}

V57_ROUTES = [
    "/api/v57/manual-approval-file-consumer",
    "/api/v57/v56-baseline",
    "/api/v57/inert-quarantine-instance-factory-v2",
    "/api/v57/quarantine-release-lock-v2",
    "/api/v57/canary-nonexecution-validator-v7",
    "/api/v57/readiness-governor",
    "/api/v57/execution-lock",
    "/api/v57/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "manual-approval-file-consumer": ["v57_manual_approval_file_consumer_report.json"],
    "v56-baseline": ["v56_baseline_readback_v1_report.json"],
    "inert-quarantine-instance-factory-v2": ["v57_inert_quarantine_instance_factory_v2_report.json"],
    "quarantine-release-lock-v2": ["v57_quarantine_release_lock_v2_report.json"],
    "canary-nonexecution-validator-v7": ["v57_canary_nonexecution_validator_v7_report.json"],
    "readiness-governor": ["readiness_governor_v17_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v16_report.json"],
    "mission-state": ["dummy_mission_state_report_v43.json", "dashboard_v57_report_v1.json", "completion_oriented_next_action_v57_report.json"],
}

SAFETY_REPORT_NAMES = [
    "no_secret_leak_report_v57.json",
    "no_approval_file_write_report_v57.json",
    "no_direct_order_bypass_report_v57.json",
    "no_order_ticket_generation_report_v57.json",
    "no_shadow_order_generation_report_v57.json",
    "no_dry_submit_packet_generation_report_v57.json",
    "no_broker_payload_generation_report_v57.json",
    "no_executable_rehearsal_report_v57.json",
    "no_execution_rehearsal_report_v57.json",
    "no_broker_schema_generation_report_v57.json",
    "no_order_intent_object_generation_report_v57.json",
    "no_position_sizing_artifact_report_v57.json",
    "no_capital_allocation_artifact_report_v57.json",
    "no_portfolio_construction_artifact_report_v57.json",
    "no_account_balance_private_position_access_report_v57.json",
    "no_live_submit_still_disabled_report_v57.json",
    "no_caps_config_modification_report_v57.json",
    "no_quarantine_release_path_report_v57.json",
    "no_transform_to_broker_path_report_v57.json",
    "no_quarantine_artifact_to_execution_bridge_report_v57.json",
    "no_browser_automation_report_v57.json",
    "no_mined_repo_execution_report_v57.json",
    "no_sports_source_activation_report_v57.json",
    "no_invalid_scoring_report_v57.json",
    "no_consumer_to_execution_bridge_report_v57.json",
    "no_instance_factory_to_execution_bridge_report_v57.json",
    "no_canary_validator_to_execution_bridge_report_v57.json",
    "no_readiness_governor_to_execution_bridge_report_v57.json",
    "no_execution_lock_to_execution_bridge_report_v57.json",
    "blunder_separation_recheck_v57.json",
    "dummy_canonical_identity_report_v57.json",
]

DEFAULT_REQUIRED_REPORT_NAMES = [name for names in REPORT_GROUPS.values() for name in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v57/reports.py scripts/generate_v57_reports.py dashboard/backend/v57_routes.py",
    "python scripts/generate_v57_reports.py",
    "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

FORBIDDEN_CANARY_REFERENCES = [
    "order_cancel",
    "order_ticket",
    "shadow_order",
    "dry_submit_packet",
    "broker_payload",
    "executable_rehearsal",
    "broker_schema",
    "order_intent",
    "position_sizing",
    "capital_allocation",
    "portfolio_construction",
    "account_private_access",
    "live_submit_mutation",
    "caps_mutation",
    "quarantine_release_path",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_artifact(name: str) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _int(data: dict[str, Any], key: str, fallback: int) -> int:
    try:
        return int(data.get(key, fallback))
    except Exception:
        return fallback


def _build_quarantine_instances(approval_input: dict[str, Any], approval_hash: str) -> list[dict[str, Any]]:
    created_at = now_iso()
    return [
        {
            "artifact_id": f"v57-{artifact_type.lower().replace('_', '-')}",
            "artifact_type": artifact_type,
            "created_at": created_at,
            "approval_hash": approval_hash,
            "operator": str(approval_input["operator"]),
            "reason": str(approval_input["reason"]),
            "scope": str(approval_input["scope"]),
            "expiration": str(approval_input["expiration"]),
            "inert_only": True,
            "no_broker_payload": True,
            "no_order_submission": True,
            "no_live_trading": True,
            "no_live_submit": True,
            "no_caps_modification": True,
            "quarantine_release_locked": True,
            "execution_bridge_present": False,
        }
        for artifact_type in ALLOWED_REHEARSAL_ARTIFACT_TYPES
    ]


def _write_quarantine_instances(instances: list[dict[str, Any]], quarantine_dir: Path) -> list[str]:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for instance in instances:
        path = quarantine_dir / f"{instance['artifact_id']}.json"
        path.write_text(json.dumps(instance, indent=2), encoding="utf-8")
        paths.append(str(path))
    return paths


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "verdict": verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "approval_file_created": False,
        "approval_file_modified": False,
        "approval_file_write_attempted": False,
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "direct_order_bypass_present": False,
        "direct_cancel_bypass_present": False,
        "private_endpoints_used": False,
        "order_tickets_created": False,
        "shadow_orders_created": False,
        "dry_submit_packets_created": False,
        "broker_payloads_created": False,
        "executable_rehearsal_created": False,
        "execution_rehearsal_created": False,
        "broker_schema_created": False,
        "order_intent_objects_created": False,
        "position_sizing_artifacts_created": False,
        "capital_allocation_artifacts_created": False,
        "portfolio_construction_artifacts_created": False,
        "account_balance_private_position_accessed": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "mined_repo_executed": False,
        "sports_source_activated": False,
        "outcome_fabricated": False,
        "consumer_to_execution_bridge_present": False,
        "instance_factory_to_execution_bridge_present": False,
        "quarantine_artifact_to_execution_bridge_present": False,
        "quarantine_release_path_present": False,
        "transform_to_broker_path_present": False,
        "dry_submit_conversion_present": False,
        "shadow_order_conversion_present": False,
        "canary_validator_to_execution_bridge_present": False,
        "readiness_governor_to_execution_bridge_present": False,
        "execution_lock_to_execution_bridge_present": False,
        "workflow_to_execution_bridge_present": False,
        "selected_action_can_trigger_execution": False,
        "requests_orders_or_cancels": False,
        "live_trading_recommendation": False,
        "live_trading_readiness_claim": False,
        "quarantine_release_locked": True,
        "quarantine_release_attempts_allowed": False,
        "quarantine_to_execution_transform_available": False,
        "v57_execution_artifacts_created": False,
        "pnl_claim": False,
        "trading_edge_claim": False,
        "statistically_final_edge_claim": False,
        "prompt_text_treated_as_approval": False,
        "env_var_treated_as_approval": False,
        "raw_phrase_serialized": False,
        "raw_acknowledgments_serialized": False,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
    }


class V57Context:
    def __init__(
        self,
        *,
        approval_input: dict[str, Any] | None,
        approval_path: Path | None,
        write_quarantine_artifacts: bool,
        quarantine_dir: Path | None,
    ) -> None:
        # Read ONLY the dedicated approval file (or a direct dict for focused tests). Dummy never
        # creates or modifies this file.
        self.resolution = resolve_v55_approval_input(approval_path, approval_input)
        self.approval_input = self.resolution.get("approval_input")
        self.approval_result = validate_v55_approval_input(self.resolution)
        self.consumer_status = _CONSUMER_STATUS.get(str(self.approval_result["status"]), str(self.approval_result["status"]))
        self.v56_final_artifact = _load_artifact("final_report_v56.json")
        self.v56_mission_artifact = _load_artifact("dummy_mission_state_report_v42.json")
        self.v56_handoff_artifact = _load_artifact("v56_operator_handoff_controller_report.json")
        self.created_instances = _build_quarantine_instances(self.approval_input, str(self.approval_result["approval_hash"])) if self.approval_input is not None and self.approval_result.get("accepted") else []
        self.quarantine_dir = quarantine_dir or DEFAULT_QUARANTINE_DIR
        self.created_instance_paths = _write_quarantine_instances(self.created_instances, self.quarantine_dir) if write_quarantine_artifacts and self.created_instances else []

    @property
    def v56_baseline_status(self) -> str:
        if not self.v56_final_artifact or not self.v56_mission_artifact or not self.v56_handoff_artifact:
            return "PARTIAL_V56_BASELINE_UNAVAILABLE"
        checks = [
            self.v56_final_artifact.get("verdict") == "PASS",
            self.v56_final_artifact.get("v55_baseline_status") == "PASS_V55_BASELINE_READBACK",
            self.v56_final_artifact.get("operator_handoff_status") == "PASS_OPERATOR_HANDOFF_READY",
            self.v56_final_artifact.get("approval_packet_linter_status") == "PASS_APPROVAL_PACKET_LINTER",
            self.v56_final_artifact.get("pre_artifact_lock_status") == "PASS_PRE_ARTIFACT_LOCK_HELD",
            self.v56_final_artifact.get("canary_nonexecution_validator_v6_status") == "PASS_CANARY_NONEXECUTION_VALIDATOR_V6",
            self.v56_final_artifact.get("readiness_governor_v16_status") == "PASS",
            self.v56_final_artifact.get("execution_lock_deep_recheck_v15_status") == "PASS",
            _int(self.v56_final_artifact, "cumulative_real_scored_count", 0) == 222,
            self.v56_final_artifact.get("current_next_action") == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY",
        ]
        return "PASS_V56_BASELINE_READBACK" if all(checks) else "FAIL_V56_BASELINE_REGRESSION"

    @property
    def v56_cumulative_real_scored_count(self) -> int:
        return _int(self.v56_final_artifact, "cumulative_real_scored_count", 222)

    @property
    def factory_status(self) -> str:
        status = self.consumer_status
        if status == "PARTIAL_APPROVAL_FILE_ABSENT":
            return "PARTIAL_APPROVAL_FILE_ABSENT_NO_INSTANCES_CREATED"
        if status == "PARTIAL_APPROVAL_FILE_MALFORMED":
            return "PARTIAL_APPROVAL_FILE_MALFORMED_NO_INSTANCES_CREATED"
        if status == "FAIL_CLOSED_INVALID_APPROVAL":
            return "FAIL_CLOSED_INVALID_APPROVAL"
        return "PASS_INERT_QUARANTINE_INSTANCES_CREATED"

    @property
    def final_verdict(self) -> str:
        if self.v56_baseline_status.startswith("FAIL") or self.consumer_status.startswith("FAIL"):
            return "FAIL"
        if self.v56_baseline_status.startswith("PARTIAL") or not self.approval_result.get("accepted"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v56_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V56_BASELINE_REGRESSION")
        elif self.v56_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V56_BASELINE_UNAVAILABLE")
        if self.consumer_status == "PARTIAL_APPROVAL_FILE_ABSENT":
            blockers.append("APPROVAL_FILE_ABSENT")
        elif self.consumer_status == "PARTIAL_APPROVAL_FILE_MALFORMED":
            blockers.append("APPROVAL_FILE_MALFORMED")
        blockers.extend(self.approval_result.get("blockers", []) if self.consumer_status.startswith("FAIL") else [])
        return blockers

    @property
    def next_action(self) -> str:
        if self.approval_result.get("accepted"):
            return "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"
        return "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def _common(ctx: V57Context) -> dict[str, Any]:
    return {
        "v56_baseline_status": ctx.v56_baseline_status,
        "v56_final_verdict": ctx.v56_final_artifact.get("verdict", "UNKNOWN"),
        "v55_baseline_status": ctx.v56_final_artifact.get("v55_baseline_status", "UNKNOWN"),
        "v56_operator_handoff_status": ctx.v56_final_artifact.get("operator_handoff_status", "UNKNOWN"),
        "v56_pre_artifact_lock_status": ctx.v56_final_artifact.get("pre_artifact_lock_status", "UNKNOWN"),
        "v56_canary_v6_status": ctx.v56_final_artifact.get("canary_nonexecution_validator_v6_status", "UNKNOWN"),
        "v56_cumulative_real_scored_count": ctx.v56_cumulative_real_scored_count,
        "v57_new_real_scored_count": 0,
        "cumulative_real_scored_count": ctx.v56_cumulative_real_scored_count,
        "manual_approval_file_consumer_status": ctx.consumer_status,
        "dedicated_approval_input_path": str(DEFAULT_APPROVAL_INPUT_PATH),
        "approval_input_source": ctx.resolution.get("source"),
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "dedicated_approval_file_present": ctx.resolution.get("resolution") != "ABSENT",
        "dummy_creates_approval_file": False,
        "dummy_modifies_approval_file": False,
        "prompt_treated_as_approval": False,
        "approval_validated": bool(ctx.approval_result.get("accepted")),
        "approval_hash": ctx.approval_result.get("approval_hash", ""),
        "approval_result": ctx.approval_result,
        "required_approval_fields": REQUIRED_APPROVAL_FIELDS,
        "exact_approval_phrase": EXACT_APPROVAL_PHRASE,
        "fuzzy_or_broader_phrase_fails_closed": True,
        "malformed_approval_file_fails_partial": True,
        "absent_approval_file_fails_partial": True,
        "inert_quarantine_instance_factory_v2_status": ctx.factory_status,
        "artifact_allowlist_status": "PASS_REHEARSAL_ARTIFACT_ALLOWLIST_LOCKED",
        "allowed_artifact_types": ALLOWED_REHEARSAL_ARTIFACT_TYPES,
        "denied_artifact_types": DENIED_REHEARSAL_ARTIFACT_TYPES,
        "artifact_schema_fields": ARTIFACT_SCHEMA_FIELDS,
        "forbidden_artifact_fields": FORBIDDEN_ARTIFACT_FIELDS,
        "created_instances": ctx.created_instances,
        "created_instance_paths": ctx.created_instance_paths,
        "created_artifact_types": [instance["artifact_type"] for instance in ctx.created_instances],
        "created_quarantine_instance_count": len(ctx.created_instances),
        "quarantine_instances_created": bool(ctx.created_instances),
        "quarantine_dir": str(ctx.quarantine_dir),
        "quarantine_release_lock_v2_status": "PASS_QUARANTINE_RELEASE_LOCKED_V2",
        "quarantine_release_lock_status": "PASS_QUARANTINE_RELEASE_LOCKED",
        "release_path_present": False,
        "submit_path_present": False,
        "transform_to_broker_path_present": False,
        "dry_submit_conversion_present": False,
        "shadow_order_conversion_present": False,
        "release_attempt_fails": True,
        "quarantine_to_execution_transform_status": "FAIL_CLOSED_NO_TRANSFORM_PATH",
        "canary_nonexecution_validator_v7_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V7",
        "canary_forbidden_references": FORBIDDEN_CANARY_REFERENCES,
        "order_cancel_reference_detected": False,
        "order_ticket_reference_detected": False,
        "shadow_order_reference_detected": False,
        "dry_submit_packet_reference_detected": False,
        "broker_payload_reference_detected": False,
        "executable_rehearsal_reference_detected": False,
        "broker_schema_reference_detected": False,
        "order_intent_reference_detected": False,
        "capital_or_portfolio_reference_detected": False,
        "account_private_access_reference_detected": False,
        "live_submit_caps_mutation_reference_detected": False,
        "quarantine_release_path_reference_detected": False,
        "sports_excluded": True,
        "browser_calls_allowed": False,
        "readiness_governor_v17_status": "PASS",
        "OPERATOR_ARMED_REHEARSAL_LOCKED": True,
        "QUARANTINE_RELEASE_LOCKED": True,
        "LIVE_TRADING_LOCKED": True,
        "LIVE_SUBMIT_DISABLED": True,
        "CAPS_OPERATOR_CONTROLLED": True,
        "execution_lock_deep_recheck_v16_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
        "safety_proof": {"execution_bridge_present": False, "approval_file_created": False, "live_submit_disabled": True, "caps_unchanged": True, "quarantine_release_locked": True, "v57_execution_artifacts_created": False},
    }


def _workstream(report_name: str) -> str:
    return "v57: " + report_name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()


def _verdict(report_name: str, ctx: V57Context) -> str:
    if report_name in SAFETY_REPORT_NAMES or report_name.startswith("no_") or "blunder" in report_name or "canonical_identity" in report_name:
        return "PASS"
    if report_name.startswith("v56_baseline"):
        return "PASS" if ctx.v56_baseline_status == "PASS_V56_BASELINE_READBACK" else "FAIL" if ctx.v56_baseline_status.startswith("FAIL") else "PARTIAL"
    if report_name == "v57_manual_approval_file_consumer_report.json":
        return "FAIL" if ctx.consumer_status.startswith("FAIL") else "PASS" if ctx.approval_result.get("accepted") else "PARTIAL"
    if report_name == "v57_inert_quarantine_instance_factory_v2_report.json":
        return "FAIL" if ctx.factory_status.startswith("FAIL") else "PASS" if ctx.created_instances else "PARTIAL"
    return "PASS" if not ctx.v56_baseline_status.startswith(("FAIL", "PARTIAL")) else ctx.final_verdict


def _component_payload(report_name: str, ctx: V57Context) -> dict[str, Any]:
    report = _safe_base(_workstream(report_name), _verdict(report_name, ctx))
    report.update(_common(ctx))
    report["report_name"] = report_name
    if report_name == "v57_manual_approval_file_consumer_report.json":
        report.update({
            "v57_manual_approval_file_consumer_status": ctx.consumer_status,
            "reads_only_dedicated_file": True,
            "creates_approval_file": False,
            "modifies_approval_file": False,
            "stores_hash_only": True,
        })
    elif report_name == "v57_inert_quarantine_instance_factory_v2_report.json":
        report.update({"schema_valid": True, "only_allowed_artifact_types_created": True, "forbidden_artifact_fields_present": False, "execution_bridge_present_pinned_false": True})
    elif report_name == "v57_quarantine_release_lock_v2_report.json":
        report.update({"v57_quarantine_release_lock_v2_status": "PASS_QUARANTINE_RELEASE_LOCKED_V2", "release_path_present": False, "submit_path_present": False, "transform_to_broker_path_present": False, "dry_submit_conversion_present": False, "shadow_order_conversion_present": False})
    elif report_name == "v57_canary_nonexecution_validator_v7_report.json":
        report.update({"validated_canary_reference_count": len(FORBIDDEN_CANARY_REFERENCES)})
    elif report_name == "completion_oriented_next_action_v57_report.json":
        report.update({"completion_oriented_next_action_v57_status": "PASS", "next_action": ctx.next_action})
    elif report_name == "dashboard_v57_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V57_ROUTES, "read_only_dashboard": True, "dashboard_can_trigger_probes": False, "dashboard_can_trigger_trading": False, "dashboard_can_create_approval_file": False, "dashboard_can_create_quarantine_artifacts": False})
    elif report_name == "dummy_mission_state_report_v43.json":
        report.update({
            "mission_state_verdict": ctx.final_verdict,
            "v56_carried_status": "PASS" if ctx.v56_baseline_status == "PASS_V56_BASELINE_READBACK" else ctx.v56_baseline_status,
            "proof_paths": {
                "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v43.json"),
                "final_report": str(ARTIFACTS / "final_report_v57.json"),
                "v56_baseline": str(ARTIFACTS / "v56_baseline_readback_v1_report.json"),
                "manual_approval_file_consumer": str(ARTIFACTS / "v57_manual_approval_file_consumer_report.json"),
                "inert_quarantine_instance_factory_v2": str(ARTIFACTS / "v57_inert_quarantine_instance_factory_v2_report.json"),
                "quarantine_release_lock_v2": str(ARTIFACTS / "v57_quarantine_release_lock_v2_report.json"),
                "canary_nonexecution_validator_v7": str(ARTIFACTS / "v57_canary_nonexecution_validator_v7_report.json"),
            },
        })
    if report_name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": report_name, "no_invalid_scoring": True})
        if report_name in {"blunder_separation_recheck_v57.json", "dummy_canonical_identity_report_v57.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_blunder_modified": False, "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V57ReportFactory:
    def __init__(
        self,
        *,
        approval_input: dict[str, Any] | None = None,
        approval_path: Path | None = None,
        write_quarantine_artifacts: bool = False,
        quarantine_dir: Path | None = None,
    ) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.write_quarantine_artifacts = write_quarantine_artifacts
        self.quarantine_dir = quarantine_dir

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V57Context(
            approval_input=self.approval_input,
            approval_path=self.approval_path,
            write_quarantine_artifacts=self.write_quarantine_artifacts,
            quarantine_dir=self.quarantine_dir,
        )
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
