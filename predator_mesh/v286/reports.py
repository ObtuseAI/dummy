"""DUMMY v286 external authority seal verifier (no write) — default blocked absent manifest; fuzzy/broad fail closed; no approval writes, no raw phrase leakage."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh import final_console_common as fcc
from predator_mesh.v286 import MILESTONE

WORKSTREAM = "v286: External Authority Seal Verifier No Write"
DASH_TITLE = "Dummy V286 External Authority Seal Verifier"
MISSION_KEY = "dummy_mission_state_report_v286"
CONTROLLER_KEY = "external_authority_seal_verifier_controller_status"

BROAD_TERMS = ["full live trading", "trade live markets", "enable live submit", "unlimited", "all markets", "grant full"]

REPORT_GROUPS: dict[str, list[str]] = {
    "external-authority-seal-verifier": ["v286_external_authority_seal_verifier_controller_report.json"],
    "v285-baseline": ["v285_baseline_readback_v1_report.json"],
    "seal-state": ["v286_seal_state_report.json"],
    "no-approval-writes-proof": ["v286_no_approval_writes_proof_report.json"],
    "no-submit-proof": ["v286_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v286_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v246_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v245_report.json"],
    "mission-state": ["dummy_mission_state_report_v286.json", "dashboard_v286_report_v1.json", "completion_oriented_next_action_v286_report.json"],
}

V286_ROUTES = [f"/api/v286/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Seal", CONTROLLER_KEY], ["State", "seal_state"], ["Next Action", "current_next_action"]]


def _evaluate(manifest: dict[str, Any] | None) -> tuple[str, str, str, dict[str, Any]]:
    """Return (status, verdict, seal_state, fields). Never serialize raw phrases."""
    if not manifest:
        return ("PARTIAL_AUTHORITY_SEAL_BLOCKED_MANIFEST_ABSENT", "PARTIAL", "SEAL_BLOCKED_MANIFEST_ABSENT",
                {"failure_code": "MANIFEST_ABSENT"})
    approvals = manifest.get("approvals", {}) or {}
    phrase = str(approvals.get("exact_phrase", ""))
    reason = str(manifest.get("reason", "")).lower()
    phrase_exact = phrase == sgc.CONTROLLED_PILOT_PHRASE
    broad = any(t in reason for t in BROAD_TERMS) or any(t in phrase.lower() for t in BROAD_TERMS)
    meta = {
        "manifest_hash": sgc.approval_hash(manifest),
        "approval_hash": sgc.approval_hash(approvals) if approvals else "",
        "phrase_exact": phrase_exact,
        "proof_target": manifest.get("proof_target"),
        "has_operator_metadata": bool(manifest.get("operator_metadata")),
        "has_expiry": bool(manifest.get("expiry")),
        "has_scope": bool(manifest.get("scope")),
    }
    if broad:
        return ("FAIL_CLOSED_AUTHORITY_SEAL_BROAD_APPROVAL_REJECTED", "PARTIAL", "SEAL_BLOCKED_APPROVAL_INVALID",
                {**meta, "failure_code": "BROAD_APPROVAL_REJECTED", "broad_language_rejected": True})
    if not phrase_exact:
        return ("FAIL_CLOSED_AUTHORITY_SEAL_APPROVAL_PHRASE_INVALID", "PARTIAL", "SEAL_BLOCKED_APPROVAL_INVALID",
                {**meta, "failure_code": "APPROVAL_PHRASE_INVALID"})
    if not manifest.get("config_descriptors"):
        return ("PARTIAL_AUTHORITY_SEAL_BLOCKED_CONFIG_CAPS", "PARTIAL", "SEAL_BLOCKED_CONFIG_CAPS",
                {**meta, "failure_code": "CONFIG_CAPS_DESCRIPTOR_ABSENT"})
    if not manifest.get("adapter_descriptors"):
        return ("PARTIAL_AUTHORITY_SEAL_BLOCKED_ADAPTER", "PARTIAL", "SEAL_BLOCKED_ADAPTER",
                {**meta, "failure_code": "ADAPTER_DESCRIPTOR_ABSENT"})
    return ("PASS_AUTHORITY_SEAL_VERIFIED_READY_FOR_ARMABILITY", "PASS", "SEAL_READY_FOR_ARMABILITY",
            {**meta, "failure_code": None, "seal_verified": True})


def _controller(baseline_status: str, manifest: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    status, verdict, seal_state, fields = _evaluate(manifest)
    return {
        "status": status,
        "verdict": verdict,
        "fields": {
            "seal_state": seal_state,
            **fields,
            "raw_phrase_serialized": False,
            "no_approval_writes_status": "PASS_NO_APPROVAL_WRITES",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [] if verdict == "PASS" else [seal_state],
        "next_action": "AUTHORITY_SEAL_" + seal_state + "_NEXT_RUN_FINAL_ARMABILITY_RUNBOOK_NO_SUBMIT" if verdict == "PASS"
        else "AUTHORITY_SEAL_" + seal_state + "_NEXT_OPERATOR_SUPPLY_EXTERNAL_AUTHORITY_NO_SUBMIT",
    }


_BUNDLE = fcc.StageBundle(
    version=286, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V286_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V286ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
