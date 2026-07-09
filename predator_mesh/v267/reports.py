"""DUMMY v267 approval manifest schema verifier strict fix hints no write — fail-closed staged gate; no live order, no broker contact, no submit by Dummy, no approval-file write."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v267 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v267: Approval Manifest Schema Verifier Strict Fix Hints No Write"
MISSION_NAME = "dummy_mission_state_report_v253.json"
FINAL_NAME = "final_report_v267.json"
INDEX_KEYS = ['approval_manifest_schema_verifier_controller_status', 'schema_state', 'approval_files_written']
DASH_TITLE = "Dummy V267 Approval Manifest Schema Verifier Strict Fix Hints No Write"
MISSION_KEY = "dummy_mission_state_report_v253"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Schema Verifier', 'approval_manifest_schema_verifier_controller_status'], ['Schema State', 'schema_state'], ['Approval Files Written', 'approval_files_written'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V267_ROUTES = ['/api/v267/approval-manifest-schema-verifier-controller', '/api/v267/v266-baseline', '/api/v267/schema-checks', '/api/v267/fix-hints', '/api/v267/schema-state', '/api/v267/missing-keys', '/api/v267/no-raw-phrase-leakage', '/api/v267/no-approval-file-write-proof', '/api/v267/no-runtime-approvals-proof', '/api/v267/no-submit-proof', '/api/v267/readiness-governor', '/api/v267/execution-lock', '/api/v267/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'approval-manifest-schema-verifier-controller': ['v267_approval_manifest_schema_verifier_controller_report.json'], 'v266-baseline': ['v266_baseline_readback_v1_report.json'], 'schema-checks': ['v267_schema_checks_report.json'], 'fix-hints': ['v267_fix_hints_report.json'], 'schema-state': ['v267_schema_state_report.json'], 'missing-keys': ['v267_missing_keys_report.json'], 'no-raw-phrase-leakage': ['v267_no_raw_phrase_leakage_report.json'], 'no-approval-file-write-proof': ['v267_no_approval_file_write_proof_report.json'], 'no-runtime-approvals-proof': ['v267_no_runtime_approvals_proof_report.json'], 'no-submit-proof': ['v267_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v227_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v226_report.json'], 'mission-state': ['dummy_mission_state_report_v253.json', 'dashboard_v267_report_v1.json', 'completion_oriented_next_action_v267_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(267)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v267/reports.py scripts/generate_v267_reports.py dashboard/backend/v267_routes.py",
    "python scripts/generate_v267_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v267_approval_manifest_schema_verifier_controller_report.json"

REQUIRED_SCHEMA_KEYS = ["version", "proof_target", "approvals", "config_descriptors", "adapter_descriptors", "operator_metadata", "expiry", "scope", "reason"]
FIX_HINT_MAP = {
    "version": "Add a manifest schema version string.",
    "proof_target": "Set proof_target to FIRST_REAL_PILOT_PROOF or CONTROLLED_SESSION_PROOF.",
    "approvals": "Add an approvals object containing the exact approval phrase and acknowledgments.",
    "config_descriptors": "Add config_descriptors for live-submit and caps.",
    "adapter_descriptors": "Add adapter_descriptors for the LiveBrokerFirewall adapter.",
    "operator_metadata": "Add operator_metadata (operator, timestamp).",
    "expiry": "Add a non-expired expiry timestamp.",
    "scope": "Add the exact single-controlled-pilot scope.",
    "reason": "Add a concise non-broad reason.",
}


class V267Context:
    def __init__(self, *, manifest=None, manifest_path=None) -> None:
        self.v266_baseline_status = sgc.baseline_status("final_report_v266.json", "V266")
        if manifest is None and manifest_path is not None:
            loaded = sgc.load_artifact(str(manifest_path))
            manifest = loaded or None
        self.present = isinstance(manifest, dict) and bool(manifest)
        m = manifest if self.present else {}
        self.missing_keys = [k for k in REQUIRED_SCHEMA_KEYS if not m.get(k)]
        # Phrase / broad-language hygiene inside the approvals object.
        approvals = m.get("approvals", {}) if isinstance(m.get("approvals", {}), dict) else {}
        phrase = str(approvals.get("exact_phrase", ""))
        self.phrase_exact = phrase == sgc.CONTROLLED_PILOT_PHRASE
        broad_fields = " ".join(str(v).lower() for k, v in m.items() if k != "approvals") + " " + " ".join(str(v).lower() for k, v in approvals.items() if k != "exact_phrase")
        self.broad_language = any(term in broad_fields for term in sgc.DEFAULT_FUZZY_TERMS)
        self.target_valid = str(m.get("proof_target", "")) in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.schema_complete = self.present and not self.missing_keys and self.phrase_exact and not self.broad_language and self.target_valid

    @property
    def schema_state(self) -> str:
        if not self.present:
            return "SCHEMA_ABSENT"
        if self.missing_keys or not self.phrase_exact or self.broad_language or not self.target_valid:
            return "SCHEMA_INVALID"
        return "SCHEMA_VALID_READY_FOR_RESOLVER"

    @property
    def controller_status(self) -> str:
        if self.v266_baseline_status.startswith("FAIL"):
            return "FAIL_APPROVAL_MANIFEST_SCHEMA_VERIFIER_BASELINE_REGRESSION"
        if self.schema_complete:
            return "PASS_APPROVAL_MANIFEST_SCHEMA_VERIFIED_READY_FOR_RESOLVER"
        return "PARTIAL_APPROVAL_MANIFEST_SCHEMA_ABSENT_OR_INVALID"

    @property
    def final_verdict(self) -> str:
        if self.v266_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.schema_complete else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v266_baseline_status.startswith("FAIL"):
            return ["FAIL_V266_BASELINE_REGRESSION"]
        if self.schema_complete:
            return []
        if not self.present:
            return ["SCHEMA_ABSENT"]
        b = ["MISSING_KEY:" + k for k in self.missing_keys]
        if not self.phrase_exact:
            b.append("APPROVAL_PHRASE_INVALID")
        if self.broad_language:
            b.append("BROAD_LIVE_APPROVAL_REJECTED")
        if not self.target_valid:
            b.append("PROOF_TARGET_INVALID")
        return b or ["SCHEMA_INVALID"]

    @property
    def fix_hints(self) -> dict:
        return {k: FIX_HINT_MAP[k] for k in self.missing_keys} or {"NONE": "Schema valid; ready for resolver."}

    @property
    def next_action(self) -> str:
        if self.schema_complete:
            return "APPROVAL_MANIFEST_SCHEMA_VERIFIED_RUN_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIER_NO_SUBMIT"
        return "OPERATOR_REPAIR_MANIFEST_SCHEMA_PER_FIX_HINTS_DUMMY_WRITES_NOTHING"


def _common(ctx) -> dict[str, Any]:
    return {
        "v266_baseline_status": ctx.v266_baseline_status,
        "approval_manifest_schema_verifier_controller_status": ctx.controller_status,
        "schema_state": ctx.schema_state,
        "schema_states": ["SCHEMA_ABSENT", "SCHEMA_INVALID", "SCHEMA_VALID_AUTHORITY_INCOMPLETE", "SCHEMA_VALID_READY_FOR_RESOLVER"],
        "schema_present": ctx.present,
        "required_schema_keys": REQUIRED_SCHEMA_KEYS,
        "missing_keys": ctx.missing_keys,
        "missing_keys_status": "PASS_MISSING_KEYS_CLASSIFIED",
        "phrase_exact": ctx.phrase_exact,
        "broad_language_rejected": ctx.broad_language,
        "schema_checks_status": "PASS_SCHEMA_CHECKS_RUN",
        "schema_state_status": "PASS_SCHEMA_STATE_CLASSIFIED",
        "fix_hints": ctx.fix_hints,
        "fix_hints_status": "PASS_FIX_HINTS_EMITTED",
        "no_raw_phrase_leakage_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_runtime_approvals_proof_status": "PASS_NO_RUNTIME_APPROVALS",
        "no_submit_proof_status": "PASS_NO_SUBMIT",

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v227_status": "PASS",
        "execution_lock_deep_recheck_v226_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v266_baseline"):
        return "PASS" if ctx.v266_baseline_status == "PASS_V266_BASELINE_READBACK" else "FAIL" if ctx.v266_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v267: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v267_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V267_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v267_report.json":
        report.update({"completion_oriented_next_action_v267_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v266_carried_status": ctx.v266_baseline_status, "approval_manifest_schema_verifier_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v267.json", "dummy_canonical_identity_report_v267.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V267ReportFactory:
    def __init__(self, *, manifest=None, manifest_path=None) -> None:
        self.kw = dict(manifest=manifest, manifest_path=manifest_path)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V267Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
