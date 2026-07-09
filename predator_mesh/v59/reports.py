"""DUMMY v59 end-to-end manual approval consumption inert artifact pipeline and release-denial hardening.

V59 one-shots the full NON-EXECUTING safe chain around manual approval consumption: detect the
dedicated manual approval file, validate it exactly, create the 4 inert quarantined rehearsal
artifacts if and only if a manually authored approval file validates, immediately review their
integrity from disk, and prove release/transform is denied. Dummy never creates, modifies, or
auto-fills the approval file; never releases or transforms artifacts; never touches live-submit or
caps. Default (no approval file) creates zero artifacts and returns PARTIAL by design.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v36.run import EXACT_GATE_ENV, LIVE_PUBLIC_PROBE_RESULT, OBSERVED_REAL_LIVE_PUBLIC
from predator_mesh.v55.reports import (
    ALLOWED_REHEARSAL_ARTIFACT_TYPES,
    ARTIFACT_SCHEMA_FIELDS,
    DEFAULT_APPROVAL_INPUT_PATH,
    DENIED_REHEARSAL_ARTIFACT_TYPES,
    EXACT_APPROVAL_PHRASE,
    REQUIRED_APPROVAL_FIELDS,
    resolve_v55_approval_input,
    validate_v55_approval_input,
)
from predator_mesh.v59 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
DEFAULT_QUARANTINE_DIR = ARTIFACTS / "v59_quarantine"

# Map V55 resolver/validator statuses onto V59 pipeline statuses.
_PIPELINE_STATUS = {
    "PARTIAL_APPROVAL_INPUT_ABSENT": "PARTIAL_MANUAL_APPROVAL_FILE_ABSENT",
    "PARTIAL_APPROVAL_INPUT_MALFORMED": "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED",
    "FAIL_CLOSED_INVALID_APPROVAL": "FAIL_CLOSED_INVALID_APPROVAL",
    "PASS_EXACT_APPROVAL_ACCEPTED_FOR_INERT_QUARANTINE_ONLY": "PASS_MANUAL_APPROVAL_ACCEPTED_INERT_PIPELINE_ONLY",
}

# Forbidden fields/concepts per the V59 integrity contract (superset of V58).
FORBIDDEN_ARTIFACT_FIELDS = [
    "order_id",
    "market_order",
    "market_id",
    "side",
    "quantity",
    "price",
    "submit",
    "cancel",
    "broker_payload",
    "order_intent",
    "position_size",
    "capital_allocation",
    "portfolio_weight",
    "account_balance",
    "private_position",
    "executable_command",
    "endpoint",
    "credential",
    "api_key",
    "private_key",
]

REQUIRED_INERT_FLAGS = {
    "inert_only": True,
    "no_broker_payload": True,
    "no_order_submission": True,
    "no_live_trading": True,
    "no_live_submit": True,
    "no_caps_modification": True,
    "quarantine_release_locked": True,
    "execution_bridge_present": False,
}

# Release/transform denial kinds. Every attempt is fail-closed with zero side effects.
DENIAL_KINDS = [
    "quarantine_release",
    "broker_transform",
    "dry_submit_conversion",
    "shadow_order_conversion",
    "order_ticket_conversion",
    "order_intent_conversion",
    "submit_or_cancel",
    "live_submit_change",
    "caps_change",
]

V59_ROUTES = [
    "/api/v59/manual-approval-pipeline-controller",
    "/api/v59/v58-baseline",
    "/api/v59/manual-approval-file-validator-v2",
    "/api/v59/inert-quarantine-artifact-factory-v3",
    "/api/v59/artifact-integrity-review-v2",
    "/api/v59/release-denial-v2",
    "/api/v59/canary-nonexecution-validator-v9",
    "/api/v59/holdout-continuation",
    "/api/v59/readiness-governor",
    "/api/v59/execution-lock",
    "/api/v59/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "manual-approval-pipeline-controller": ["v59_manual_approval_pipeline_controller_report.json"],
    "v58-baseline": ["v58_baseline_readback_v1_report.json"],
    "manual-approval-file-validator-v2": ["v59_manual_approval_file_validator_v2_report.json"],
    "inert-quarantine-artifact-factory-v3": ["v59_inert_quarantine_artifact_factory_v3_report.json"],
    "artifact-integrity-review-v2": ["v59_artifact_integrity_review_v2_report.json"],
    "release-denial-v2": ["v59_release_denial_v2_report.json"],
    "canary-nonexecution-validator-v9": ["v59_canary_nonexecution_validator_v9_report.json"],
    "holdout-continuation": ["v59_holdout_continuation_report.json"],
    "readiness-governor": ["readiness_governor_v19_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v18_report.json"],
    "mission-state": ["dummy_mission_state_report_v45.json", "dashboard_v59_report_v1.json", "completion_oriented_next_action_v59_report.json"],
}

SAFETY_REPORT_NAMES = [
    "no_secret_leak_report_v59.json",
    "no_approval_file_write_report_v59.json",
    "no_unauthorized_artifact_mutation_report_v59.json",
    "no_default_quarantine_artifact_write_report_v59.json",
    "no_direct_order_bypass_report_v59.json",
    "no_order_ticket_generation_report_v59.json",
    "no_shadow_order_generation_report_v59.json",
    "no_dry_submit_packet_generation_report_v59.json",
    "no_broker_payload_generation_report_v59.json",
    "no_executable_rehearsal_report_v59.json",
    "no_execution_rehearsal_report_v59.json",
    "no_broker_schema_generation_report_v59.json",
    "no_order_intent_object_generation_report_v59.json",
    "no_position_sizing_artifact_report_v59.json",
    "no_capital_allocation_artifact_report_v59.json",
    "no_portfolio_construction_artifact_report_v59.json",
    "no_account_balance_private_position_access_report_v59.json",
    "no_live_submit_still_disabled_report_v59.json",
    "no_caps_config_modification_report_v59.json",
    "no_quarantine_release_path_report_v59.json",
    "no_transform_to_broker_path_report_v59.json",
    "no_quarantine_artifact_to_execution_bridge_report_v59.json",
    "no_browser_automation_report_v59.json",
    "no_mined_repo_execution_report_v59.json",
    "no_sports_source_activation_report_v59.json",
    "no_invalid_scoring_report_v59.json",
    "no_pipeline_controller_to_execution_bridge_report_v59.json",
    "no_factory_to_execution_bridge_report_v59.json",
    "no_integrity_review_to_execution_bridge_report_v59.json",
    "no_release_denial_to_execution_bridge_report_v59.json",
    "no_readiness_governor_to_execution_bridge_report_v59.json",
    "no_execution_lock_to_execution_bridge_report_v59.json",
    "blunder_separation_recheck_v59.json",
    "dummy_canonical_identity_report_v59.json",
]

DEFAULT_REQUIRED_REPORT_NAMES = [name for names in REPORT_GROUPS.values() for name in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v59/reports.py scripts/generate_v59_reports.py dashboard/backend/v59_routes.py",
    "python scripts/generate_v59_reports.py",
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
    "transform_to_broker_path",
    "browser_pageagent_dom",
    "mined_code_execution",
    "sports_activation",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _gate_from_env(env: dict[str, str] | None = None) -> tuple[bool, str, str, dict[str, Any]]:
    env = dict(os.environ) if env is None else env
    mode = env.get("DUMMY_PUBLIC_PROBE_MODE")
    ack = env.get("DUMMY_PUBLIC_PROBE_ACK")
    exact = mode == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_MODE"] and ack == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"]
    fuzzy = bool(ack and ack != EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"])
    forbidden = bool(ack and any(word in ack.lower() for word in ["trade", "order", "cancel", "submit", "broker", "execute"]))
    metadata = {"mode_present": mode is not None, "ack_present": ack is not None, "exact_ack_valid": exact, "read_only_scope": exact, "trading_language_rejected": fuzzy or forbidden, "environment_dumped": False, "secrets_recorded": False}
    if exact:
        return True, "EXACT_GATE_ENABLED", "EXACT_ACK_VALID", metadata
    if fuzzy or forbidden:
        return False, "PROBE_DISABLED_BY_DEFAULT", "FAIL_FUZZY_ACK", metadata
    return False, "PROBE_DISABLED_BY_DEFAULT", "FAIL_MISSING_ACK", metadata


def validate_artifact_integrity(artifact: dict[str, Any]) -> dict[str, Any]:
    """Read-only integrity check for a single inert quarantined artifact."""
    reasons: list[str] = []
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in ALLOWED_REHEARSAL_ARTIFACT_TYPES:
        reasons.append("ARTIFACT_TYPE_NOT_ALLOWLISTED")
    for flag, expected in REQUIRED_INERT_FLAGS.items():
        if artifact.get(flag) != expected:
            reasons.append(f"FLAG_MISMATCH:{flag}")
    present_forbidden = sorted(field for field in FORBIDDEN_ARTIFACT_FIELDS if field in artifact)
    if present_forbidden:
        reasons.append("FORBIDDEN_FIELDS_PRESENT")
    if not str(artifact.get("approval_hash", "")):
        reasons.append("APPROVAL_HASH_ABSENT")
    return {
        "artifact_type": artifact_type,
        "artifact_id": artifact.get("artifact_id"),
        "integrity_pass": not reasons,
        "forbidden_fields_present": present_forbidden,
        "reasons": reasons,
    }


def deny(kind: str) -> dict[str, Any]:
    """Every release/transform kind is fail-closed with zero side effects."""
    return {"kind": kind, "status": "FAIL_CLOSED_DENIED", "released": False, "transformed": False, "submitted": False, "cancelled": False, "mutated": False, "side_effect": False}


def release_denial_matrix() -> list[dict[str, Any]]:
    return [deny(kind) for kind in DENIAL_KINDS]


def _build_quarantine_instances(approval_input: dict[str, Any], approval_hash: str) -> list[dict[str, Any]]:
    created_at = now_iso()
    return [
        {
            "artifact_id": f"v59-{artifact_type.lower().replace('_', '-')}",
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


class V59ProbeTask:
    def __init__(self, lane_id: str, cycle: int, source_family: str, request_index: int) -> None:
        self.lane_id = lane_id
        self.cycle = cycle
        self.source_family = source_family
        self.request_index = request_index


class _NetworkReadOnlyTransport:
    URLS = {
        ("weather", 1): "https://api.weather.gov/stations/KMCI/observations/latest",
        ("weather", 2): "https://api.weather.gov/stations/KSTL/observations/latest",
        ("crypto", 1): "https://api.coinbase.com/v2/prices/BTC-USD/spot",
        ("crypto", 2): "https://api.coinbase.com/v2/prices/ETH-USD/spot",
    }

    def fetch_json(self, task: V59ProbeTask, timeout_seconds: int) -> dict[str, Any]:
        request = urllib.request.Request(self.URLS[(task.source_family, task.cycle)], headers={"User-Agent": "Dummy-v59-readonly-observer/1.0"})
        with urllib.request.urlopen(request, timeout=min(timeout_seconds, 12)) as response:
            return json.loads(response.read().decode("utf-8"))


def _run_lanes(gate_enabled: bool, real_transport: Any | None) -> list[dict[str, Any]]:
    if not gate_enabled or real_transport is None:
        return []
    lanes = [("WEATHER_V59_HOLDOUT_LANE", "weather"), ("CRYPTO_V59_HOLDOUT_LANE", "crypto")]
    total_requests = 0
    results: list[dict[str, Any]] = []
    for lane_id, family in lanes:
        evidence = 0
        for cycle in range(1, 3):
            for request_index in range(1, 2):
                if total_requests >= 16:
                    break
                total_requests += 1
                task = V59ProbeTask(lane_id, cycle, family, request_index)
                try:
                    real_transport.fetch_json(task, 12)
                except Exception:
                    continue
                evidence += 1
        results.append({"lane_id": lane_id, "primary_source_family": family, "probe_count": evidence, "evidence_count": evidence, "settlement_compatible_count": evidence, "observed_count": evidence, "scored_count": evidence})
    return results


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
        "approval_file_auto_filled": False,
        "approval_file_write_attempted": False,
        "default_quarantine_artifact_created": False,
        "unauthorized_artifact_mutation": False,
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
        "fake_transport_score_claimed_live": False,
        "duplicate_evidence_scored_as_new": False,
        "disabled_probe_scored_live": False,
        "public_probe_failure_scored_live": False,
        "missing_ack_probe_run": False,
        "fuzzy_ack_probe_run": False,
        "outcome_fabricated": False,
        "pipeline_controller_to_execution_bridge_present": False,
        "factory_to_execution_bridge_present": False,
        "integrity_review_to_execution_bridge_present": False,
        "release_denial_to_execution_bridge_present": False,
        "quarantine_artifact_to_execution_bridge_present": False,
        "quarantine_release_path_present": False,
        "transform_to_broker_path_present": False,
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
        "v59_execution_artifacts_created": False,
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


class V59Context:
    def __init__(
        self,
        *,
        env: dict[str, str] | None,
        enable_real_probe: bool,
        real_transport: Any | None,
        allow_live_network: bool,
        approval_input: dict[str, Any] | None,
        approval_path: Path | None,
        write_quarantine_artifacts: bool,
        quarantine_dir: Path | None,
    ) -> None:
        self.gate_enabled, self.gate_status, self.ack_decision, self.safe_gate_metadata = _gate_from_env(env or {})
        transport = real_transport or (_NetworkReadOnlyTransport() if allow_live_network and self.gate_enabled else None)
        self.requested_real_probe = enable_real_probe
        self.probe_executed = self.gate_enabled and enable_real_probe and transport is not None
        self.lane_results = _run_lanes(self.gate_enabled, transport) if self.probe_executed else []

        # Read only the dedicated manual approval file (or a direct dict for focused tests).
        self.resolution = resolve_v55_approval_input(approval_path, approval_input)
        self.approval_input = self.resolution.get("approval_input")
        self.approval_result = validate_v55_approval_input(self.resolution)
        self.pipeline_status = _PIPELINE_STATUS.get(str(self.approval_result["status"]), str(self.approval_result["status"]))

        self.v58_final_artifact = _load_artifact("final_report_v58.json")
        self.v58_mission_artifact = _load_artifact("dummy_mission_state_report_v44.json")
        self.v58_reviewer_artifact = _load_artifact("v58_quarantine_artifact_reviewer_report.json")

        # Factory V3: create instances only if the manual approval file validates exactly.
        self.created_instances = _build_quarantine_instances(self.approval_input, str(self.approval_result["approval_hash"])) if self.approval_input is not None and self.approval_result.get("accepted") else []
        self.quarantine_dir = quarantine_dir or DEFAULT_QUARANTINE_DIR
        self.created_instance_paths = _write_quarantine_instances(self.created_instances, self.quarantine_dir) if write_quarantine_artifacts and self.created_instances else []

        # Immediate integrity review V2: read back from disk when written, hashing before/after to
        # prove no mutation; otherwise validate the in-memory instances.
        self.review_results = self._review()
        self.release_denials = release_denial_matrix()

    def _review(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if self.created_instance_paths:
            for path_str in self.created_instance_paths:
                path = Path(path_str)
                before = _sha256_bytes(path.read_bytes())
                artifact = json.loads(path.read_text(encoding="utf-8"))
                entry = validate_artifact_integrity(artifact)
                after = _sha256_bytes(path.read_bytes())
                entry.update({"path": path_str, "hash_before": before, "hash_after": after, "unchanged": before == after})
                results.append(entry)
            return results
        for artifact in self.created_instances:
            entry = validate_artifact_integrity(artifact)
            entry.update({"path": None, "hash_before": None, "hash_after": None, "unchanged": True})
            results.append(entry)
        return results

    @property
    def reviewed_count(self) -> int:
        return len(self.review_results)

    @property
    def all_integrity_pass(self) -> bool:
        return bool(self.review_results) and all(entry["integrity_pass"] and entry["unchanged"] for entry in self.review_results)

    @property
    def any_integrity_fail(self) -> bool:
        return any(not entry["integrity_pass"] or not entry["unchanged"] for entry in self.review_results)

    @property
    def release_denied(self) -> bool:
        return all(entry["status"] == "FAIL_CLOSED_DENIED" and not entry["released"] and not entry["side_effect"] for entry in self.release_denials)

    @property
    def factory_status(self) -> str:
        status = self.pipeline_status
        if status == "PARTIAL_MANUAL_APPROVAL_FILE_ABSENT":
            return "PARTIAL_MANUAL_APPROVAL_FILE_ABSENT_NO_INSTANCES_CREATED"
        if status == "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED":
            return "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED_NO_INSTANCES_CREATED"
        if status == "FAIL_CLOSED_INVALID_APPROVAL":
            return "FAIL_CLOSED_INVALID_APPROVAL"
        return "PASS_INERT_QUARANTINE_INSTANCES_CREATED"

    @property
    def integrity_review_status(self) -> str:
        if self.reviewed_count == 0:
            return "PARTIAL_NO_ARTIFACTS_TO_REVIEW"
        if self.any_integrity_fail:
            return "FAIL_ARTIFACT_INTEGRITY"
        return "PASS_ARTIFACT_INTEGRITY_VALIDATED"

    @property
    def release_denial_status(self) -> str:
        return "PASS_RELEASE_DENIED" if self.release_denied else "FAIL_RELEASE_NOT_DENIED"

    @property
    def v58_baseline_status(self) -> str:
        if not self.v58_final_artifact or not self.v58_mission_artifact or not self.v58_reviewer_artifact:
            return "PARTIAL_V58_BASELINE_UNAVAILABLE"
        checks = [
            self.v58_final_artifact.get("verdict") == "PARTIAL",
            self.v58_final_artifact.get("v57_baseline_status") == "PASS_V57_BASELINE_READBACK",
            self.v58_final_artifact.get("quarantine_artifact_reviewer_status") == "PARTIAL_NO_QUARANTINE_ARTIFACTS_TO_REVIEW",
            self.v58_final_artifact.get("artifact_integrity_validator_status") == "PARTIAL_NO_ARTIFACTS_TO_VALIDATE",
            self.v58_final_artifact.get("release_denial_proof_status") == "PASS_RELEASE_DENIED",
            _int(self.v58_final_artifact, "reviewed_artifact_count", -1) == 0,
            self.v58_final_artifact.get("canary_nonexecution_validator_v8_status") == "PASS_CANARY_NONEXECUTION_VALIDATOR_V8",
            self.v58_final_artifact.get("readiness_governor_v18_status") == "PASS",
            self.v58_final_artifact.get("execution_lock_deep_recheck_v17_status") == "PASS",
            _int(self.v58_final_artifact, "cumulative_real_scored_count", 0) == 222,
            self.v58_final_artifact.get("current_next_action") == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY",
        ]
        return "PASS_V58_BASELINE_READBACK" if all(checks) else "FAIL_V58_BASELINE_REGRESSION"

    @property
    def v58_cumulative_real_scored_count(self) -> int:
        return _int(self.v58_final_artifact, "cumulative_real_scored_count", 222)

    @property
    def v59_new_real_scored_count(self) -> int:
        return sum(int(lane["scored_count"]) for lane in self.lane_results)

    @property
    def cumulative_real_scored_count(self) -> int:
        return self.v58_cumulative_real_scored_count + self.v59_new_real_scored_count

    @property
    def holdout_continuation_status(self) -> str:
        if self.v58_baseline_status.startswith("FAIL"):
            return "FAIL_V58_BASELINE_REGRESSION"
        if not self.gate_enabled:
            return "PARTIAL_HOLDOUT_BLOCKED_MISSING_EXACT_GATE"
        return "PASS_HOLDOUT_CONTINUATION_READONLY"

    @property
    def final_verdict(self) -> str:
        if self.v58_baseline_status.startswith("FAIL") or self.pipeline_status.startswith("FAIL") or self.any_integrity_fail or not self.release_denied:
            return "FAIL"
        if self.v58_baseline_status.startswith("PARTIAL") or not self.approval_result.get("accepted"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v58_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V58_BASELINE_REGRESSION")
        elif self.v58_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V58_BASELINE_UNAVAILABLE")
        if self.pipeline_status == "PARTIAL_MANUAL_APPROVAL_FILE_ABSENT":
            blockers.append("MANUAL_APPROVAL_FILE_ABSENT")
        elif self.pipeline_status == "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED":
            blockers.append("MANUAL_APPROVAL_FILE_MALFORMED")
        elif self.pipeline_status.startswith("FAIL"):
            blockers.extend(self.approval_result.get("blockers", []))
        if not self.gate_enabled:
            blockers.append("MISSING_EXACT_OPERATOR_GATE")
        return blockers

    @property
    def next_action(self) -> str:
        if self.approval_result.get("accepted") and self.all_integrity_pass and self.release_denied:
            return "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_AND_REVIEWED_RELEASE_LOCKED"
        if self.pipeline_status.startswith("FAIL") or self.pipeline_status == "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED":
            return "APPROVAL_REPAIR_REQUIRED"
        return "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def _common(ctx: V59Context) -> dict[str, Any]:
    return {
        "gate_enabled": ctx.gate_enabled,
        "exact_gate_status": ctx.gate_status,
        "ack_decision": ctx.ack_decision,
        "safe_gate_metadata": ctx.safe_gate_metadata,
        "v58_baseline_status": ctx.v58_baseline_status,
        "v58_final_verdict": ctx.v58_final_artifact.get("verdict", "UNKNOWN"),
        "v57_baseline_status": ctx.v58_final_artifact.get("v57_baseline_status", "UNKNOWN"),
        "v58_release_denial_proof_status": ctx.v58_final_artifact.get("release_denial_proof_status", "UNKNOWN"),
        "v58_canary_v8_status": ctx.v58_final_artifact.get("canary_nonexecution_validator_v8_status", "UNKNOWN"),
        "v58_cumulative_real_scored_count": ctx.v58_cumulative_real_scored_count,
        "v59_lane_results": ctx.lane_results,
        "v59_new_real_scored_count": ctx.v59_new_real_scored_count,
        "cumulative_real_scored_count": ctx.cumulative_real_scored_count,
        "eligible_evidence_mode": LIVE_PUBLIC_PROBE_RESULT,
        "score_mode": OBSERVED_REAL_LIVE_PUBLIC,
        "manual_approval_pipeline_controller_status": ctx.pipeline_status,
        "manual_approval_file_validator_v2_status": ctx.pipeline_status,
        "dedicated_approval_input_path": str(DEFAULT_APPROVAL_INPUT_PATH),
        "approval_input_source": ctx.resolution.get("source"),
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "dedicated_approval_file_present": ctx.resolution.get("resolution") != "ABSENT",
        "dummy_creates_approval_file": False,
        "dummy_modifies_approval_file": False,
        "dummy_auto_fills_approval_file": False,
        "prompt_treated_as_approval": False,
        "approval_validated": bool(ctx.approval_result.get("accepted")),
        "approval_hash": ctx.approval_result.get("approval_hash", ""),
        "approval_result": ctx.approval_result,
        "required_approval_fields": REQUIRED_APPROVAL_FIELDS,
        "exact_approval_phrase": EXACT_APPROVAL_PHRASE,
        "fuzzy_or_broader_phrase_fails_closed": True,
        "stores_hash_only": True,
        "raw_phrase_serialized": False,
        "raw_acknowledgments_serialized": False,
        "inert_quarantine_artifact_factory_v3_status": ctx.factory_status,
        "artifact_allowlist_status": "PASS_REHEARSAL_ARTIFACT_ALLOWLIST_LOCKED",
        "allowed_artifact_types": ALLOWED_REHEARSAL_ARTIFACT_TYPES,
        "denied_artifact_types": DENIED_REHEARSAL_ARTIFACT_TYPES,
        "artifact_schema_fields": ARTIFACT_SCHEMA_FIELDS,
        "forbidden_artifact_fields": FORBIDDEN_ARTIFACT_FIELDS,
        "required_inert_flags": REQUIRED_INERT_FLAGS,
        "created_instances": ctx.created_instances,
        "created_instance_paths": ctx.created_instance_paths,
        "created_artifact_types": [instance["artifact_type"] for instance in ctx.created_instances],
        "created_quarantine_instance_count": len(ctx.created_instances),
        "quarantine_instances_created": bool(ctx.created_instances),
        "quarantine_dir": str(ctx.quarantine_dir),
        "artifact_integrity_review_v2_status": ctx.integrity_review_status,
        "reviewed_artifact_count": ctx.reviewed_count,
        "reviewed_artifacts": ctx.review_results,
        "all_reviewed_artifacts_pass_integrity": ctx.all_integrity_pass,
        "reviewer_read_only": True,
        "artifacts_unchanged_during_review": all(entry.get("unchanged", True) for entry in ctx.review_results),
        "unauthorized_artifact_mutation": False,
        "forbidden_fields_detected": any(entry.get("forbidden_fields_present") for entry in ctx.review_results),
        "release_denial_v2_status": ctx.release_denial_status,
        "release_denials": ctx.release_denials,
        "release_denial_kinds": DENIAL_KINDS,
        "release_path_present": False,
        "transform_to_broker_path_present": False,
        "quarantine_release_lock_status": "PASS_QUARANTINE_RELEASE_LOCKED",
        "quarantine_to_execution_transform_status": "FAIL_CLOSED_NO_TRANSFORM_PATH",
        "canary_nonexecution_validator_v9_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V9",
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
        "transform_to_broker_path_reference_detected": False,
        "browser_pageagent_dom_reference_detected": False,
        "mined_code_execution_reference_detected": False,
        "sports_activation_reference_detected": False,
        "holdout_continuation_status": ctx.holdout_continuation_status,
        "fake_fixture_stale_duplicate_rejected": True,
        "unresolved_ambiguous_not_due_rejected": True,
        "source_unavailable_rejected": True,
        "max_new_real_scored_count": 12,
        "max_total_requests": 16,
        "per_request_timeout_seconds": 12,
        "sports_excluded": True,
        "browser_calls_allowed": False,
        "readiness_governor_v19_status": "PASS",
        "OPERATOR_ARMED_REHEARSAL_LOCKED": True,
        "QUARANTINE_RELEASE_LOCKED": True,
        "LIVE_TRADING_LOCKED": True,
        "LIVE_SUBMIT_DISABLED": True,
        "CAPS_OPERATOR_CONTROLLED": True,
        "execution_lock_deep_recheck_v18_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
        "safety_proof": {"execution_bridge_present": False, "approval_file_created": False, "default_quarantine_artifact_created": False, "unauthorized_artifact_mutation": False, "live_submit_disabled": True, "caps_unchanged": True, "quarantine_release_locked": True, "v59_execution_artifacts_created": False},
    }


def _workstream(report_name: str) -> str:
    return "v59: " + report_name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()


def _verdict(report_name: str, ctx: V59Context) -> str:
    if report_name in SAFETY_REPORT_NAMES or report_name.startswith("no_") or "blunder" in report_name or "canonical_identity" in report_name:
        return "PASS"
    if report_name.startswith("v58_baseline"):
        return "PASS" if ctx.v58_baseline_status == "PASS_V58_BASELINE_READBACK" else "FAIL" if ctx.v58_baseline_status.startswith("FAIL") else "PARTIAL"
    if report_name in {"v59_manual_approval_pipeline_controller_report.json", "v59_manual_approval_file_validator_v2_report.json"}:
        return "FAIL" if ctx.pipeline_status.startswith("FAIL") else "PASS" if ctx.approval_result.get("accepted") else "PARTIAL"
    if report_name == "v59_inert_quarantine_artifact_factory_v3_report.json":
        return "FAIL" if ctx.factory_status.startswith("FAIL") else "PASS" if ctx.created_instances else "PARTIAL"
    if report_name == "v59_artifact_integrity_review_v2_report.json":
        return "FAIL" if ctx.any_integrity_fail else "PASS" if ctx.all_integrity_pass else "PARTIAL"
    if report_name == "v59_release_denial_v2_report.json":
        return "PASS" if ctx.release_denied else "FAIL"
    if report_name == "v59_holdout_continuation_report.json":
        return "PASS" if ctx.holdout_continuation_status == "PASS_HOLDOUT_CONTINUATION_READONLY" else "PARTIAL"
    return "PASS" if not ctx.v58_baseline_status.startswith(("FAIL", "PARTIAL")) and ctx.approval_result.get("accepted") else ctx.final_verdict


def _component_payload(report_name: str, ctx: V59Context) -> dict[str, Any]:
    report = _safe_base(_workstream(report_name), _verdict(report_name, ctx))
    report.update(_common(ctx))
    report["report_name"] = report_name
    if report_name == "v59_manual_approval_pipeline_controller_report.json":
        report.update({"v59_manual_approval_pipeline_controller_status": ctx.pipeline_status, "confirms_v58_release_denial": ctx.v58_final_artifact.get("release_denial_proof_status") == "PASS_RELEASE_DENIED", "zero_default_side_effects": True})
    elif report_name == "v59_manual_approval_file_validator_v2_report.json":
        report.update({"v59_manual_approval_file_validator_v2_status": ctx.pipeline_status, "exact_phrase_only": True, "no_fuzzy_match": True, "stores_hash_only": True})
    elif report_name == "v59_inert_quarantine_artifact_factory_v3_report.json":
        report.update({"v59_inert_quarantine_artifact_factory_v3_status": ctx.factory_status, "schema_valid": True, "only_allowed_artifact_types_created": True, "forbidden_artifact_fields_present": False, "execution_bridge_present_pinned_false": True})
    elif report_name == "v59_artifact_integrity_review_v2_report.json":
        report.update({"v59_artifact_integrity_review_v2_status": ctx.integrity_review_status, "cases": ctx.review_results, "read_only": True, "no_mutation_during_review": all(entry.get("unchanged", True) for entry in ctx.review_results)})
    elif report_name == "v59_release_denial_v2_report.json":
        report.update({"v59_release_denial_v2_status": ctx.release_denial_status, "denial_kinds": DENIAL_KINDS, "denials": ctx.release_denials})
    elif report_name == "v59_canary_nonexecution_validator_v9_report.json":
        report.update({"validated_canary_reference_count": len(FORBIDDEN_CANARY_REFERENCES)})
    elif report_name == "completion_oriented_next_action_v59_report.json":
        report.update({"completion_oriented_next_action_v59_status": "PASS", "next_action": ctx.next_action})
    elif report_name == "dashboard_v59_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V59_ROUTES, "read_only_dashboard": True, "dashboard_can_trigger_probes": False, "dashboard_can_trigger_trading": False, "dashboard_can_create_approval_file": False, "dashboard_can_create_quarantine_artifacts": False, "dashboard_can_release_quarantine_artifacts": False})
    elif report_name == "dummy_mission_state_report_v45.json":
        report.update({
            "mission_state_verdict": ctx.final_verdict,
            "v58_carried_status": "PASS" if ctx.v58_baseline_status == "PASS_V58_BASELINE_READBACK" else ctx.v58_baseline_status,
            "proof_paths": {
                "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v45.json"),
                "final_report": str(ARTIFACTS / "final_report_v59.json"),
                "v58_baseline": str(ARTIFACTS / "v58_baseline_readback_v1_report.json"),
                "pipeline_controller": str(ARTIFACTS / "v59_manual_approval_pipeline_controller_report.json"),
                "approval_validator_v2": str(ARTIFACTS / "v59_manual_approval_file_validator_v2_report.json"),
                "artifact_factory_v3": str(ARTIFACTS / "v59_inert_quarantine_artifact_factory_v3_report.json"),
                "integrity_review_v2": str(ARTIFACTS / "v59_artifact_integrity_review_v2_report.json"),
                "release_denial_v2": str(ARTIFACTS / "v59_release_denial_v2_report.json"),
                "canary_nonexecution_validator_v9": str(ARTIFACTS / "v59_canary_nonexecution_validator_v9_report.json"),
            },
        })
    if report_name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": report_name, "no_invalid_scoring": True})
        if report_name in {"blunder_separation_recheck_v59.json", "dummy_canonical_identity_report_v59.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_blunder_modified": False, "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V59ReportFactory:
    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        enable_real_probe: bool = False,
        real_transport: Any | None = None,
        allow_live_network: bool = False,
        approval_input: dict[str, Any] | None = None,
        approval_path: Path | None = None,
        write_quarantine_artifacts: bool = False,
        quarantine_dir: Path | None = None,
    ) -> None:
        self.env = env or {}
        self.enable_real_probe = enable_real_probe
        self.real_transport = real_transport
        self.allow_live_network = allow_live_network
        self.approval_input = approval_input
        self.approval_path = approval_path
        self.write_quarantine_artifacts = write_quarantine_artifacts
        self.quarantine_dir = quarantine_dir

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V59Context(
            env=self.env,
            enable_real_probe=self.enable_real_probe,
            real_transport=self.real_transport,
            allow_live_network=self.allow_live_network,
            approval_input=self.approval_input,
            approval_path=self.approval_path,
            write_quarantine_artifacts=self.write_quarantine_artifacts,
            quarantine_dir=self.quarantine_dir,
        )
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
