from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v255_reports import generate_all_v255_reports_for_tests
from archive.report_scripts.generate_v256_reports import generate_all_v256_reports_for_tests
from archive.report_scripts.generate_v257_reports import generate_all_v257_reports_for_tests
from archive.report_scripts.generate_v258_reports import generate_all_v258_reports_for_tests
from archive.report_scripts.generate_v259_reports import generate_all_v259_reports_for_tests
from archive.report_scripts.generate_v260_reports import generate_all_v260_reports_for_tests
from archive.report_scripts.generate_v261_reports import generate_all_v261_reports_for_tests
from archive.report_scripts.generate_v262_reports import generate_all_v262_reports_for_tests
from archive.report_scripts.generate_v263_reports import generate_all_v263_reports_for_tests
from archive.report_scripts.generate_v264_reports import generate_all_v264_reports_for_tests
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


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("real_broker_contacted") is False
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False


# --- V255 execution appliance baseline (always PASS) ---
def test_v255_execution_appliance_baseline_ready() -> None:
    d = generate_all_v255_reports_for_tests()["v255_operator_execution_appliance_baseline_controller_report.json"]
    assert d["operator_execution_appliance_baseline_controller_status"] == "PASS_OPERATOR_EXECUTION_APPLIANCE_BASELINE_READY"
    assert d["appliance_state_classification"]
    _safe(d)


# --- V256 single-command operator pipeline (dry default) ---
def test_v256_single_command_pipeline_dry() -> None:
    d = generate_all_v256_reports_for_tests()["v256_single_command_operator_pipeline_controller_report.json"]
    assert d["single_command_operator_pipeline_controller_status"] == "PASS_SINGLE_COMMAND_OPERATOR_PIPELINE_COMPLETE_DRY"
    assert d["dry_mode"] is True and d["firewall_submit_invoked"] is False and d["broker_contacted"] is False
    assert len(d["pipeline_stages"]) == 10
    _safe(d)


# --- V257 authority manifest validator V3 (exact/fuzzy/broad) ---
def test_v257_default_absent_fixture_pass_fuzzy_broad_fail() -> None:
    d = generate_all_v257_reports_for_tests()["v257_authority_manifest_validator_controller_report.json"]
    assert d["authority_manifest_validator_controller_status"] == "PARTIAL_AUTHORITY_MANIFEST_VALIDATOR_BLOCKED_INPUTS_ABSENT"
    assert d["failure_code"] == "MANIFEST_ABSENT" and d["approval_files_written"] == 0
    ok = generate_all_v257_reports_for_tests(manifest_approval=pilot_approval())["v257_authority_manifest_validator_controller_report.json"]
    assert ok["authority_manifest_validator_controller_status"] == "PASS_AUTHORITY_MANIFEST_VALIDATOR_V3_READY"
    assert ok["manifest_valid"] is True and ok["fix_hint"]
    fuzzy = generate_all_v257_reports_for_tests(manifest_approval=pilot_approval("bad"))["v257_authority_manifest_validator_controller_report.json"]
    assert fuzzy["authority_manifest_validator_controller_status"] == "FAIL_CLOSED_AUTHORITY_MANIFEST_VALIDATOR_REJECTED"
    assert fuzzy["failure_code"] == "PHRASE_MISMATCH"
    broad = generate_all_v257_reports_for_tests(manifest_approval=pilot_approval(sgc.CONTROLLED_PILOT_PHRASE) | {"reason": "grant full live trading authority to trade live markets"})["v257_authority_manifest_validator_controller_report.json"]
    assert broad["authority_manifest_validator_controller_status"] == "FAIL_CLOSED_AUTHORITY_MANIFEST_VALIDATOR_REJECTED"
    assert broad["failure_code"] == "BROAD_LIVE_APPROVAL_REJECTED"
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("manifest_approval_hash", ""))
    _safe(ok)


# --- V258 live adapter smoke kit (non-broker double) ---
def test_v258_default_awaits_and_non_broker_double_ready() -> None:
    d = generate_all_v258_reports_for_tests()["v258_adapter_smoke_kit_controller_report.json"]
    assert d["adapter_smoke_kit_controller_status"] == "PARTIAL_LIVE_ADAPTER_SMOKE_KIT_AWAITS_EXTERNAL_ADAPTER"
    ok = generate_all_v258_reports_for_tests(firewall_adapter=FakeFirewall("smoke"))["v258_adapter_smoke_kit_controller_report.json"]
    assert ok["adapter_smoke_kit_controller_status"] == "PASS_LIVE_ADAPTER_SMOKE_KIT_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False and ok["live_orders"] == 0
    _safe(ok)


# --- V259 live-submit/caps final rehearsal V2 (immutable hashes) ---
def test_v259_default_blocked_and_fixture_ready_hashes_unchanged() -> None:
    d = generate_all_v259_reports_for_tests()["v259_live_submit_caps_final_rehearsal_controller_report.json"]
    assert d["live_submit_caps_final_rehearsal_controller_status"] == "PARTIAL_LIVE_SUBMIT_CAPS_FINAL_REHEARSAL_BLOCKED"
    assert d["live_submit_hash_unchanged"] is True and d["caps_hash_unchanged"] is True
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    ok = generate_all_v259_reports_for_tests(config_confirmed_override=True)["v259_live_submit_caps_final_rehearsal_controller_report.json"]
    assert ok["live_submit_caps_final_rehearsal_controller_status"] == "PASS_LIVE_SUBMIT_CAPS_FINAL_REHEARSAL_READY_IMMUTABLE"
    assert ok["live_submit_hash_unchanged"] is True and ok["caps_hash_unchanged"] is True
    _safe(ok)


# --- V260 pre-execution freeze V2 (blocked by missing authority) ---
def test_v260_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v260_reports_for_tests()["v260_pre_execution_freeze_v2_controller_report.json"]
    assert d["pre_execution_freeze_v2_controller_status"] == "PARTIAL_PRE_EXECUTION_FREEZE_V2_BLOCKED_BY_MISSING_AUTHORITY"
    assert d["resolver_state"] == "LIVE_BLOCKED_AUTHORITY_ABSENT"
    ok = generate_all_v260_reports_for_tests(armable_override=True, manifest_override=True, config_override=True, adapter_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK)["v260_pre_execution_freeze_v2_controller_report.json"]
    assert ok["pre_execution_freeze_v2_controller_status"] == "PASS_PRE_EXECUTION_FREEZE_V2_READY_NO_SUBMIT"
    assert ok["resolver_state"] == "LIVE_PROOF_ARMABLE" and ok["total_real_live_orders_submitted"] == 0
    _safe(ok)


# --- V261 execute-once final harness V4 (only fire surface) ---
def test_v261_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v261_reports_for_tests()["v261_execute_once_final_harness_controller_report.json"]
    assert d["execute_once_final_harness_controller_status"] == "PARTIAL_EXECUTE_ONCE_FINAL_HARNESS_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v261_reports_for_tests(
        proof_approval=pilot_approval(), freeze_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
        mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True,
        caps_config_present=True, firewall_adapter=FakeFirewall("v261-attempt-1"),
    )["v261_execute_once_final_harness_controller_report.json"]
    assert c["execute_once_final_harness_controller_status"] == "PASS_EXECUTE_ONCE_FINAL_HARNESS_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v261-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    _safe(c)


def test_v261_blocks_missing_env_freeze_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), freeze_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
                mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v261_execute_once_final_harness_controller_report.json"
    for key, val in [("env_gate_mode", False), ("freeze_override", False), ("proof_approval", pilot_approval("bad")), ("firewall_adapter", None)]:
        r = generate_all_v261_reports_for_tests(**{**base, key: val})[ctrl]
        assert r["firewall_submit_invoked"] is False and r["live_orders"] == 0


# --- V262 external proof intake V2 (default no attempt) ---
def test_v262_default_no_attempt_and_override_ready() -> None:
    d = generate_all_v262_reports_for_tests()["v262_external_proof_intake_v2_controller_report.json"]
    assert d["external_proof_intake_v2_controller_status"] == "PARTIAL_NO_EXTERNAL_PROOF_TO_INGEST"
    assert d["intake_state"] == "NO_ATTEMPT"
    r = generate_all_v262_reports_for_tests(
        v261_final_override={"execute_once_final_harness_controller_status": "PASS_EXECUTE_ONCE_FINAL_HARNESS_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"})["v262_external_proof_intake_v2_controller_report.json"]
    assert r["external_proof_intake_v2_controller_status"] == "PASS_EXTERNAL_PROOF_INTAKE_V2_READY_FOR_RECONCILE"
    assert r["intake_state"] == "ATTEMPT_READY_FOR_RECONCILE" and r["new_order_placed"] is False
    _safe(r)


# --- V263 reconcile/forensic auto pipeline V4 (default no proof) ---
def test_v263_default_partial_and_override_reviewed() -> None:
    d = generate_all_v263_reports_for_tests()["v263_reconcile_forensic_auto_pipeline_v4_controller_report.json"]
    assert d["reconcile_forensic_auto_pipeline_v4_controller_status"] == "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC_REVIEW"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v263_reports_for_tests(
        v262_final_override={"external_proof_intake_v2_controller_status": "PASS_EXTERNAL_PROOF_INTAKE_V2_READY_FOR_RECONCILE", "proof_target": "FIRST_REAL_PILOT_PROOF"}, outcome_state="FILLED")["v263_reconcile_forensic_auto_pipeline_v4_controller_report.json"]
    assert r["reconcile_forensic_auto_pipeline_v4_controller_status"] == "PASS_RECONCILE_FORENSIC_AUTO_PIPELINE_V4_REVIEWED_LOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    _safe(r)


# --- V264 completion lift V6 (fixtures never inflate real proof) ---
def test_v264_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v264_reports_for_tests()["v264_completion_lift_v6_controller_report.json"]
    assert d["completion_lift_v6_controller_status"] == "PASS_COMPLETION_LIFT_V6_FIRST_PROOF_READY_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    _safe(d)


# --- safety / locks / no-runtime-approvals default across the whole bundle ---
def test_v255_to_v264_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v255_reports_for_tests, generate_all_v256_reports_for_tests, generate_all_v257_reports_for_tests,
        generate_all_v258_reports_for_tests, generate_all_v259_reports_for_tests, generate_all_v260_reports_for_tests,
        generate_all_v261_reports_for_tests, generate_all_v262_reports_for_tests, generate_all_v263_reports_for_tests,
        generate_all_v264_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v257_reports_for_tests, generate_all_v260_reports_for_tests, generate_all_v261_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
