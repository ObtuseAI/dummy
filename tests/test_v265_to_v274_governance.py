from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v265_reports import generate_all_v265_reports_for_tests
from scripts.generate_v266_reports import generate_all_v266_reports_for_tests
from scripts.generate_v267_reports import generate_all_v267_reports_for_tests
from scripts.generate_v268_reports import generate_all_v268_reports_for_tests
from scripts.generate_v269_reports import generate_all_v269_reports_for_tests
from scripts.generate_v270_reports import generate_all_v270_reports_for_tests
from scripts.generate_v271_reports import generate_all_v271_reports_for_tests
from scripts.generate_v272_reports import generate_all_v272_reports_for_tests
from scripts.generate_v273_reports import generate_all_v273_reports_for_tests
from scripts.generate_v274_reports import generate_all_v274_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
ROOT = Path(sgc.ROOT)


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-06T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-07T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


def valid_manifest() -> dict:
    return {
        "version": "v3", "proof_target": "FIRST_REAL_PILOT_PROOF",
        "approvals": {"exact_phrase": sgc.CONTROLLED_PILOT_PHRASE, "acknowledgments": "no market order; strict caps"},
        "config_descriptors": {"live_submit": True, "caps": True}, "adapter_descriptors": {"firewall": True},
        "operator_metadata": {"operator": "operator:chris", "timestamp": "2026-07-06T21:00:00Z"},
        "expiry": "2026-07-07T21:00:00Z", "scope": sgc.CONTROLLED_PILOT_SCOPE, "reason": "controlled pilot",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


class FakeReadonly:
    readonly = True
    allowed_calls = ["get_positions", "get_orders", "get_account_readonly"]


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("real_broker_contacted") is False
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False


# --- V265 external authority import baseline (always PASS) ---
def test_v265_external_authority_import_baseline_ready() -> None:
    d = generate_all_v265_reports_for_tests()["v265_external_authority_import_baseline_controller_report.json"]
    assert d["external_authority_import_baseline_controller_status"] == "PASS_EXTERNAL_AUTHORITY_IMPORT_BASELINE_READY"
    assert d["appliance_state_classification"]
    assert d["canonical_next_action_list"]
    _safe(d)


# --- V266 external authority import wizard (validate-only, no write) ---
def test_v266_default_absent_fixture_pass_fuzzy_broad_fail() -> None:
    ctrl = "v266_external_authority_import_wizard_controller_report.json"
    d = generate_all_v266_reports_for_tests()[ctrl]
    assert d["external_authority_import_wizard_controller_status"] == "PARTIAL_EXTERNAL_AUTHORITY_IMPORT_WIZARD_BLOCKED_INPUTS_ABSENT"
    assert d["failure_code"] == "IMPORT_MANIFEST_ABSENT" and d["approval_files_written"] == 0
    ok = generate_all_v266_reports_for_tests(import_approval=pilot_approval(), live_submit_descriptor=True, caps_descriptor=True, firewall_descriptor=True)[ctrl]
    assert ok["external_authority_import_wizard_controller_status"] == "PASS_EXTERNAL_AUTHORITY_IMPORT_WIZARD_VALIDATED_NO_WRITE"
    assert ok["wizard_valid"] is True
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("import_approval_hash", ""))
    fuzzy = generate_all_v266_reports_for_tests(import_approval=pilot_approval("bad"), live_submit_descriptor=True, caps_descriptor=True, firewall_descriptor=True)[ctrl]
    assert fuzzy["external_authority_import_wizard_controller_status"] == "FAIL_CLOSED_EXTERNAL_AUTHORITY_IMPORT_WIZARD_REJECTED"
    assert fuzzy["failure_code"] == "APPROVAL_PHRASE_INVALID"
    broad = generate_all_v266_reports_for_tests(import_approval=pilot_approval(sgc.CONTROLLED_PILOT_PHRASE) | {"reason": "grant full live trading approval to trade live markets"}, live_submit_descriptor=True, caps_descriptor=True, firewall_descriptor=True)[ctrl]
    assert broad["external_authority_import_wizard_controller_status"] == "FAIL_CLOSED_EXTERNAL_AUTHORITY_IMPORT_WIZARD_REJECTED"
    assert broad["failure_code"] == "BROAD_APPROVAL_REJECTED"
    _safe(ok)


# --- V267 approval manifest schema verifier (exact/fuzzy/broad) ---
def test_v267_default_absent_fixture_ready_fuzzy_broad_invalid() -> None:
    ctrl = "v267_approval_manifest_schema_verifier_controller_report.json"
    d = generate_all_v267_reports_for_tests()[ctrl]
    assert d["approval_manifest_schema_verifier_controller_status"] == "PARTIAL_APPROVAL_MANIFEST_SCHEMA_ABSENT_OR_INVALID"
    assert d["schema_state"] == "SCHEMA_ABSENT"
    ok = generate_all_v267_reports_for_tests(manifest=valid_manifest())[ctrl]
    assert ok["approval_manifest_schema_verifier_controller_status"] == "PASS_APPROVAL_MANIFEST_SCHEMA_VERIFIED_READY_FOR_RESOLVER"
    assert ok["schema_state"] == "SCHEMA_VALID_READY_FOR_RESOLVER"
    fuzzy_m = valid_manifest(); fuzzy_m["approvals"] = {"exact_phrase": "bad"}
    fuzzy = generate_all_v267_reports_for_tests(manifest=fuzzy_m)[ctrl]
    assert fuzzy["approval_manifest_schema_verifier_controller_status"] == "PARTIAL_APPROVAL_MANIFEST_SCHEMA_ABSENT_OR_INVALID"
    assert fuzzy["phrase_exact"] is False and fuzzy["schema_state"] == "SCHEMA_INVALID"
    broad_m = valid_manifest(); broad_m["reason"] = "enable live submit and trade live markets"
    broad = generate_all_v267_reports_for_tests(manifest=broad_m)[ctrl]
    assert broad["approval_manifest_schema_verifier_controller_status"] == "PARTIAL_APPROVAL_MANIFEST_SCHEMA_ABSENT_OR_INVALID"
    assert broad["broad_language_rejected"] is True
    _safe(ok)


# --- V268 external live-submit/caps state verifier (immutable hashes) ---
def test_v268_default_blocked_and_fixture_ready_hashes_unchanged() -> None:
    ctrl = "v268_external_live_submit_caps_state_verifier_controller_report.json"
    d = generate_all_v268_reports_for_tests()[ctrl]
    assert d["external_live_submit_caps_state_verifier_controller_status"] == "PARTIAL_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_BLOCKED"
    assert d["live_submit_hash_unchanged"] is True and d["caps_hash_unchanged"] is True
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    ok = generate_all_v268_reports_for_tests(config_confirmed_override=True)[ctrl]
    assert ok["external_live_submit_caps_state_verifier_controller_status"] == "PASS_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_IMMUTABLE"
    assert ok["live_submit_hash_unchanged"] is True and ok["caps_hash_unchanged"] is True
    assert ok["live_submit_changed"] is False and ok["caps_changed"] is False
    _safe(ok)


# --- V269 livebrokerfirewall injection appliance (non-broker double) ---
def test_v269_default_awaits_and_non_broker_double_ready() -> None:
    ctrl = "v269_livebrokerfirewall_injection_appliance_controller_report.json"
    d = generate_all_v269_reports_for_tests()[ctrl]
    assert d["livebrokerfirewall_injection_appliance_controller_status"] == "PARTIAL_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_AWAITS_EXTERNAL_ADAPTER"
    ok = generate_all_v269_reports_for_tests(firewall_adapter=FakeFirewall("inject"))[ctrl]
    assert ok["livebrokerfirewall_injection_appliance_controller_status"] == "PASS_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False and ok["live_orders"] == 0 and ok["real_adapter_generated"] is False
    _safe(ok)


# --- V270 broker read-only optional verifier (non-broker double) ---
def test_v270_default_skipped_and_non_broker_double_ready() -> None:
    ctrl = "v270_broker_readonly_optional_verifier_controller_report.json"
    d = generate_all_v270_reports_for_tests()[ctrl]
    assert d["broker_readonly_optional_verifier_controller_status"] == "PARTIAL_BROKER_READONLY_OPTIONAL_VERIFIER_BLOCKED_OR_SKIPPED"
    ok = generate_all_v270_reports_for_tests(readonly_adapter=FakeReadonly(), readonly_approved=True)[ctrl]
    assert ok["broker_readonly_optional_verifier_controller_status"] == "PASS_BROKER_READONLY_OPTIONAL_VERIFIER_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False and ok["forbidden_calls_absent"] is True
    _safe(ok)


# --- V271 final armability runbook (blocked default) ---
def test_v271_default_blocked_and_fixture_ready() -> None:
    ctrl = "v271_final_armability_runbook_controller_report.json"
    d = generate_all_v271_reports_for_tests()[ctrl]
    assert d["final_armability_runbook_controller_status"] == "PARTIAL_FINAL_ARMABILITY_RUNBOOK_BLOCKED"
    assert d["resolver_state"] == "LIVE_BLOCKED_AUTHORITY_ABSENT"
    ok = generate_all_v271_reports_for_tests(import_override=True, schema_override=True, caps_override=True, adapter_override=True, freeze_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK)[ctrl]
    assert ok["final_armability_runbook_controller_status"] == "PASS_FINAL_ARMABILITY_RUNBOOK_READY_NO_SUBMIT"
    assert ok["resolver_state"] == "LIVE_PROOF_ARMABLE" and ok["armability_state"] == "ARMABILITY_READY_NO_SUBMIT"
    assert ok["total_real_live_orders_submitted"] == 0
    _safe(ok)


# --- V272 execute-once runbook wrapper V5 (only fire surface) ---
def test_v272_default_not_armed_and_full_auth_double() -> None:
    ctrl = "v272_execute_once_runbook_controller_report.json"
    d = generate_all_v272_reports_for_tests()[ctrl]
    assert d["execute_once_runbook_controller_status"] == "PARTIAL_EXECUTE_ONCE_RUNBOOK_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v272_reports_for_tests(
        proof_approval=pilot_approval(), armability_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
        mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True,
        caps_config_present=True, firewall_adapter=FakeFirewall("v272-attempt-1"),
    )[ctrl]
    assert c["execute_once_runbook_controller_status"] == "PASS_EXECUTE_ONCE_RUNBOOK_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v272-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    _safe(c)


def test_v272_blocks_missing_env_armability_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), armability_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
                mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v272_execute_once_runbook_controller_report.json"
    for key, val in [("env_gate_mode", False), ("armability_override", False), ("proof_approval", pilot_approval("bad")), ("firewall_adapter", None)]:
        r = generate_all_v272_reports_for_tests(**{**base, key: val})[ctrl]
        assert r["firewall_submit_invoked"] is False and r["live_orders"] == 0
    # market order must never be submitted even under full auth (order shape is limit-only)
    full = generate_all_v272_reports_for_tests(**base)[ctrl]
    assert full["market_order_submitted"] is False


# --- V273 proof intake / reconcile handoff V3 (default no attempt) ---
def test_v273_default_no_attempt_and_override_ready() -> None:
    ctrl = "v273_proof_intake_reconcile_handoff_v3_controller_report.json"
    d = generate_all_v273_reports_for_tests()[ctrl]
    assert d["proof_intake_reconcile_handoff_v3_controller_status"] == "PARTIAL_NO_PROOF_ATTEMPT_TO_HANDOFF"
    assert d["handoff_state"] == "NO_ATTEMPT"
    r = generate_all_v273_reports_for_tests(
        v272_final_override={"execute_once_runbook_controller_status": "PASS_EXECUTE_ONCE_RUNBOOK_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"})[ctrl]
    assert r["proof_intake_reconcile_handoff_v3_controller_status"] == "PASS_PROOF_INTAKE_RECONCILE_HANDOFF_READY_LOCKED"
    assert r["handoff_state"] == "ATTEMPT_READY_FOR_RECONCILE" and r["new_order_placed"] is False
    _safe(r)


# --- V274 completion lift V7 (fixtures never inflate real proof) ---
def test_v274_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v274_reports_for_tests()["v274_completion_lift_v7_controller_report.json"]
    assert d["completion_lift_v7_controller_status"] == "PASS_COMPLETION_LIFT_V7_ROUTE_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    assert d["route_locked"] is True
    _safe(d)


# --- safety / locks / no-runtime-approvals default across the whole bundle ---
def test_v265_to_v274_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v265_reports_for_tests, generate_all_v266_reports_for_tests, generate_all_v267_reports_for_tests,
        generate_all_v268_reports_for_tests, generate_all_v269_reports_for_tests, generate_all_v270_reports_for_tests,
        generate_all_v271_reports_for_tests, generate_all_v272_reports_for_tests, generate_all_v273_reports_for_tests,
        generate_all_v274_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v266_reports_for_tests, generate_all_v271_reports_for_tests, generate_all_v272_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
