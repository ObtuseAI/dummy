from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v235_reports import generate_all_v235_reports_for_tests
from scripts.generate_v236_reports import generate_all_v236_reports_for_tests
from scripts.generate_v237_reports import generate_all_v237_reports_for_tests
from scripts.generate_v238_reports import generate_all_v238_reports_for_tests
from scripts.generate_v239_reports import generate_all_v239_reports_for_tests
from scripts.generate_v240_reports import generate_all_v240_reports_for_tests
from scripts.generate_v241_reports import generate_all_v241_reports_for_tests
from scripts.generate_v242_reports import generate_all_v242_reports_for_tests
from scripts.generate_v243_reports import generate_all_v243_reports_for_tests
from scripts.generate_v244_reports import generate_all_v244_reports_for_tests
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


def broker_readonly_approval(phrase: str = sgc.BROKER_READONLY_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-06T21:00:00Z",
        "reason": "broker read-only verification only", "scope": sgc.BROKER_READONLY_SCOPE,
        "expiration": "2026-07-07T21:00:00Z",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


class ReadOnlyDouble:
    def read_only_verify(self):
        return {"submit_capable": False, "real_broker_contacted": False, "connectivity": "ok"}


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False


# --- V235 appliance baseline (always PASS) ---
def test_v235_appliance_baseline_ready() -> None:
    d = generate_all_v235_reports_for_tests()["v235_operator_authority_appliance_baseline_controller_report.json"]
    assert d["operator_authority_appliance_baseline_controller_status"] == "PASS_OPERATOR_AUTHORITY_APPLIANCE_BASELINE_READY"
    assert d["appliance_blocker_classification"]
    _safe(d)


# --- V236 authority manifest doctor (validate only) ---
def test_v236_default_absent_fixture_pass_fuzzy_fail() -> None:
    d = generate_all_v236_reports_for_tests()["v236_authority_manifest_doctor_controller_report.json"]
    assert d["authority_manifest_doctor_controller_status"] == "PARTIAL_AUTHORITY_MANIFEST_ABSENT_OR_INCOMPLETE"
    assert d["failure_code"] == "MANIFEST_ABSENT" and d["approval_files_written"] == 0
    ok = generate_all_v236_reports_for_tests(manifest_approval=pilot_approval())["v236_authority_manifest_doctor_controller_report.json"]
    assert ok["authority_manifest_doctor_controller_status"] == "PASS_AUTHORITY_MANIFEST_DOCTOR_VALIDATED_EXTERNAL_INPUTS"
    assert ok["manifest_valid"] is True and ok["approval_files_written"] == 0
    fuzzy = generate_all_v236_reports_for_tests(manifest_approval=pilot_approval("bad"))["v236_authority_manifest_doctor_controller_report.json"]
    assert fuzzy["authority_manifest_doctor_controller_status"] == "FAIL_CLOSED_AUTHORITY_MANIFEST_REJECTED"
    assert fuzzy["failure_code"] == "PHRASE_MISMATCH"
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("manifest_approval_hash", ""))
    _safe(ok)


# --- V237 live-submit / caps doctor (read-only immutable) ---
def test_v237_default_blocked_fixture_ready_hashes_unchanged() -> None:
    d = generate_all_v237_reports_for_tests()["v237_live_submit_caps_doctor_controller_report.json"]
    assert d["live_submit_caps_doctor_controller_status"] == "PARTIAL_LIVE_SUBMIT_CAPS_DOCTOR_BLOCKED"
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    assert d["live_submit_hash_unchanged"] is True and d["caps_hash_unchanged"] is True
    ok = generate_all_v237_reports_for_tests(live_submit_confirmed_override=True, caps_confirmed_override=True)["v237_live_submit_caps_doctor_controller_report.json"]
    assert ok["live_submit_caps_doctor_controller_status"] == "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE"
    assert ok["live_submit_hash_unchanged"] is True and ok["caps_hash_unchanged"] is True
    assert ok["live_submit_changed"] is False and ok["caps_changed"] is False
    _safe(ok)


# --- V238 firewall adapter doctor (non-broker double) ---
def test_v238_default_blocked_and_non_broker_double_ready() -> None:
    d = generate_all_v238_reports_for_tests()["v238_firewall_adapter_doctor_controller_report.json"]
    assert d["firewall_adapter_doctor_controller_status"] == "PARTIAL_FIREWALL_ADAPTER_DOCTOR_BLOCKED"
    assert d["failure_code"] == "ADAPTER_DESCRIPTOR_ABSENT" and d["real_broker_contacted"] is False
    ok = generate_all_v238_reports_for_tests(firewall_adapter=FakeFirewall("probe"), adapter_descriptor_present=True)["v238_firewall_adapter_doctor_controller_report.json"]
    assert ok["firewall_adapter_doctor_controller_status"] == "PASS_FIREWALL_ADAPTER_DOCTOR_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False and ok["live_orders"] == 0
    _safe(ok)


# --- V239 broker read-only doctor (non-broker double) ---
def test_v239_default_blocked_and_non_broker_double_ready() -> None:
    d = generate_all_v239_reports_for_tests()["v239_broker_readonly_doctor_controller_report.json"]
    assert d["broker_readonly_doctor_controller_status"] == "PARTIAL_BROKER_READONLY_DOCTOR_BLOCKED"
    assert d["failure_code"] == "BROKER_READONLY_APPROVAL_ABSENT" and d["real_broker_contacted"] is False
    ok = generate_all_v239_reports_for_tests(readonly_approval=broker_readonly_approval(), readonly_adapter=ReadOnlyDouble())["v239_broker_readonly_doctor_controller_report.json"]
    assert ok["broker_readonly_doctor_controller_status"] == "PASS_BROKER_READONLY_DOCTOR_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False
    _safe(ok)


# --- V240 armable quorum doctor ---
def test_v240_default_blocked_and_override_armable() -> None:
    d = generate_all_v240_reports_for_tests()["v240_armable_quorum_doctor_controller_report.json"]
    assert d["armable_quorum_doctor_controller_status"] == "PARTIAL_ARMABLE_QUORUM_BLOCKED"
    assert d["resolver_explanation"] in ("BLOCKED_MANIFEST", "BLOCKED_CONFIG_CAPS", "BLOCKED_ADAPTER", "BLOCKED_BROKER_READONLY", "BLOCKED_ENV_GATE", "BLOCKED_MODE")
    ok = generate_all_v240_reports_for_tests(quorum_override=True)["v240_armable_quorum_doctor_controller_report.json"]
    assert ok["armable_quorum_doctor_controller_status"] == "PASS_ARMABLE_QUORUM_READY_NO_SUBMIT"
    assert ok["resolver_explanation"] == "ARMABLE"
    _safe(ok)


# --- V241 execute-once handoff (always PASS, blocked-by-default) ---
def test_v241_execute_once_handoff_ready_blocked_by_default() -> None:
    d = generate_all_v241_reports_for_tests()["v241_execute_once_handoff_controller_report.json"]
    assert d["execute_once_handoff_controller_status"] == "PASS_EXECUTE_ONCE_HANDOFF_READY_BLOCKED_BY_DEFAULT"
    assert d["exact_command"].startswith("DUMMY_LIVE_PROOF_MODE=1")
    assert all(d["block_proofs"].values())
    assert d["total_real_live_orders_submitted"] == 0
    _safe(d)


# --- V242 execute-once harness V2 (only fire surface) ---
def test_v242_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v242_reports_for_tests()["v242_execute_once_harness_controller_report.json"]
    assert d["execute_once_harness_controller_status"] == "PARTIAL_EXECUTE_ONCE_HARNESS_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v242_reports_for_tests(
        proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
        mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True,
        caps_config_present=True, firewall_adapter=FakeFirewall("v242-attempt-1"),
    )["v242_execute_once_harness_controller_report.json"]
    assert c["execute_once_harness_controller_status"] == "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v242-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    _safe(c)


def test_v242_blocks_missing_env_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
                mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v242_execute_once_harness_controller_report.json"
    for key, val in [("env_gate_mode", False), ("armable_override", False), ("proof_approval", pilot_approval("bad")), ("firewall_adapter", None)]:
        r = generate_all_v242_reports_for_tests(**{**base, key: val})[ctrl]
        assert r["firewall_submit_invoked"] is False and r["live_orders"] == 0


# --- V243 reconcile / forensic pipeline V2 ---
def test_v243_default_partial_and_override_reviewed() -> None:
    d = generate_all_v243_reports_for_tests()["v243_reconcile_forensic_pipeline_v2_controller_report.json"]
    assert d["reconcile_forensic_pipeline_v2_controller_status"] == "PARTIAL_NO_EXECUTE_ONCE_PROOF_TO_RECONCILE_OR_REVIEW"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v243_reports_for_tests(
        v242_final_override={"execute_once_harness_controller_status": "PASS_EXECUTE_ONCE_HARNESS_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"},
        outcome_state="FILLED")["v243_reconcile_forensic_pipeline_v2_controller_report.json"]
    assert r["reconcile_forensic_pipeline_v2_controller_status"] == "PASS_RECONCILE_FORENSIC_PIPELINE_V2_REVIEWED_LOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    _safe(r)


# --- V244 completion lift lock V4 (always PASS; fixtures never inflate real-proof score) ---
def test_v244_completion_lift_generated_no_fixture_inflation() -> None:
    d = generate_all_v244_reports_for_tests()["v244_completion_lift_lock_v4_controller_report.json"]
    assert d["completion_lift_lock_v4_controller_status"] == "PASS_COMPLETION_LIFT_LOCK_V4_GENERATED"
    assert isinstance(d["fully_operational_estimate"], int)
    # No REAL env-gated proof exists in tests -> first_live_proof stays 0, fixtures never inflate.
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["next_action_matrix_selection"] in ("FIX_MANIFEST", "FIX_LIVE_SUBMIT_CAPS", "FIX_FIREWALL_ADAPTER", "FIX_BROKER_READONLY", "RUN_ARMABLE_QUORUM_DOCTOR", "RUN_EXECUTE_ONCE_WITH_AUTHORITY")
    _safe(d)


# --- safety / locks / no-runtime-approvals default across the whole bundle ---
def test_v235_to_v244_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v235_reports_for_tests, generate_all_v236_reports_for_tests, generate_all_v237_reports_for_tests,
        generate_all_v238_reports_for_tests, generate_all_v239_reports_for_tests, generate_all_v240_reports_for_tests,
        generate_all_v241_reports_for_tests, generate_all_v242_reports_for_tests, generate_all_v243_reports_for_tests,
        generate_all_v244_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v236_reports_for_tests, generate_all_v239_reports_for_tests, generate_all_v242_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
