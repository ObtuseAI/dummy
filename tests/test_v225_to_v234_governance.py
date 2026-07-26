from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v225_reports_for_tests
from predator_mesh.report_runtime import generate_all_v226_reports_for_tests
from predator_mesh.report_runtime import generate_all_v227_reports_for_tests
from predator_mesh.report_runtime import generate_all_v228_reports_for_tests
from predator_mesh.report_runtime import generate_all_v229_reports_for_tests
from predator_mesh.report_runtime import generate_all_v230_reports_for_tests
from predator_mesh.report_runtime import generate_all_v231_reports_for_tests
from predator_mesh.report_runtime import generate_all_v232_reports_for_tests
from predator_mesh.report_runtime import generate_all_v233_reports_for_tests
from predator_mesh.report_runtime import generate_all_v234_reports_for_tests
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


def _no_runtime_approvals(report: dict) -> None:
    assert report.get("runtime_approvals_created_by_dummy") is False


# --- V225 activation pipeline baseline (always PASS) ---
def test_v225_activation_pipeline_baseline_ready() -> None:
    d = generate_all_v225_reports_for_tests()["v225_activation_pipeline_baseline_controller_report.json"]
    assert d["activation_pipeline_baseline_controller_status"] == "PASS_ACTIVATION_PIPELINE_BASELINE_READY"
    assert d["approval_files_written"] == 0 and d["total_real_live_orders_submitted"] == 0
    assert d["real_broker_contacted"] is False
    _no_runtime_approvals(d)
    assert_staged_safe(d)


# --- V226 manifest pack (read-only, always PASS) ---
def test_v226_manifest_pack_ready_readonly() -> None:
    d = generate_all_v226_reports_for_tests()["v226_manifest_pack_controller_report.json"]
    assert d["manifest_pack_controller_status"] == "PASS_MANIFEST_PACK_READY_READONLY"
    assert d["approval_files_written"] == 0
    assert d["required_approval_files_list"] and d["manifest_pack_template"]
    _no_runtime_approvals(d)
    assert_staged_safe(d)


# --- V227 one-command dry pipeline (always PASS, no contact) ---
def test_v227_one_command_dry_pipeline_complete() -> None:
    d = generate_all_v227_reports_for_tests()["v227_one_command_dry_pipeline_controller_report.json"]
    assert d["one_command_dry_pipeline_controller_status"] == "PASS_ONE_COMMAND_DRY_PIPELINE_COMPLETE"
    assert d["broker_contacted"] is False and d["firewall_submit_invoked"] is False
    assert d["dry_mode"] is True and d["live_orders"] == 0
    _no_runtime_approvals(d)
    assert_staged_safe(d)


# --- V228 external authority intake V2 (validate only) ---
def test_v228_default_absent_and_fixture_valid_no_write() -> None:
    d = generate_all_v228_reports_for_tests()["v228_external_authority_intake_v2_controller_report.json"]
    assert d["external_authority_intake_v2_controller_status"] == "PARTIAL_EXTERNAL_AUTHORITY_INTAKE_ABSENT_OR_INCOMPLETE"
    assert d["approval_files_written"] == 0 and d["intake_valid"] is False
    ok = generate_all_v228_reports_for_tests(intake_approval=pilot_approval())["v228_external_authority_intake_v2_controller_report.json"]
    assert ok["external_authority_intake_v2_controller_status"] == "PASS_EXTERNAL_AUTHORITY_INTAKE_VALIDATED_NO_SUBMIT"
    assert ok["intake_valid"] is True and ok["approval_files_written"] == 0
    fuzzy = generate_all_v228_reports_for_tests(intake_approval=pilot_approval("bad"))["v228_external_authority_intake_v2_controller_report.json"]
    assert fuzzy["external_authority_intake_v2_controller_status"] == "FAIL_CLOSED_EXTERNAL_AUTHORITY_INTAKE_REJECTED"
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("intake_approval_hash", ""))
    _no_runtime_approvals(ok)
    assert_staged_safe(ok)


# --- V229 final resolver + arming (no submit) ---
def test_v229_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v229_reports_for_tests()["v229_final_resolver_arming_controller_report.json"]
    assert d["final_resolver_arming_controller_status"] == "PARTIAL_FINAL_RESOLVER_ARMING_BLOCKED"
    assert d["arming_ready"] is False and d["live_orders"] == 0
    ok = generate_all_v229_reports_for_tests(arming_override=True)["v229_final_resolver_arming_controller_report.json"]
    assert ok["final_resolver_arming_controller_status"] == "PASS_FINAL_RESOLVER_ARMING_READY_NO_SUBMIT"
    assert ok["arming_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V230 live-proof execution orchestrator (only fire surface) ---
def test_v230_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v230_reports_for_tests()["v230_live_proof_execution_orchestrator_controller_report.json"]
    assert d["live_proof_execution_orchestrator_controller_status"] == "PARTIAL_LIVE_PROOF_EXECUTION_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v230_reports_for_tests(
        proof_approval=pilot_approval(), arming_override=True, armable_override=True, env_gate_mode=True,
        env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF",
        live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v230-attempt-1"),
    )["v230_live_proof_execution_orchestrator_controller_report.json"]
    assert c["live_proof_execution_orchestrator_controller_status"] == "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v230-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v230_blocks_missing_env_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), arming_override=True, armable_override=True, env_gate_mode=True,
                env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, live_submit_operator_enabled=True,
                caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v230_live_proof_execution_orchestrator_controller_report.json"
    no_env = generate_all_v230_reports_for_tests(**{**base, "env_gate_mode": False})[ctrl]
    assert no_env["firewall_submit_invoked"] is False and no_env["live_orders"] == 0
    no_arm = generate_all_v230_reports_for_tests(**{**base, "arming_override": False})[ctrl]
    assert no_arm["firewall_submit_invoked"] is False
    no_auth = generate_all_v230_reports_for_tests(**{**base, "armable_override": False})[ctrl]
    assert no_auth["firewall_submit_invoked"] is False
    fuzzy = generate_all_v230_reports_for_tests(**{**base, "proof_approval": pilot_approval("bad")})[ctrl]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v230_reports_for_tests(**{**base, "firewall_adapter": None})[ctrl]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V231 reconcile + forensic pipeline ---
def test_v231_default_partial_and_override_complete() -> None:
    d = generate_all_v231_reports_for_tests()["v231_reconcile_forensic_pipeline_controller_report.json"]
    assert d["reconcile_forensic_pipeline_controller_status"] == "PARTIAL_NO_LIVE_PROOF_TO_RECONCILE_OR_REVIEW"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v231_reports_for_tests(
        v230_final_override={"live_proof_execution_orchestrator_controller_status": "PASS_LIVE_PROOF_EXECUTION_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"},
        outcome_state="FILLED")["v231_reconcile_forensic_pipeline_controller_report.json"]
    assert r["reconcile_forensic_pipeline_controller_status"] == "PASS_RECONCILE_FORENSIC_PIPELINE_COMPLETE_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V232 proof-aware route decision ---
def test_v232_default_blocked_and_fixture_routed() -> None:
    d = generate_all_v232_reports_for_tests()["v232_route_decision_controller_report.json"]
    assert d["route_state"] == "ROUTE_BLOCKED_NO_LIVE_PROOF"
    ok = generate_all_v232_reports_for_tests(first_proof_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF")["v232_route_decision_controller_report.json"]
    assert ok["route_decision_controller_status"] == "PASS_ROUTE_DECISION_READY_LOCKED"
    assert ok["route_state"] == "ROUTE_REPEAT_PILOT_REVIEW_READY"
    sess = generate_all_v232_reports_for_tests(first_proof_override=True, proof_target_override="CONTROLLED_SESSION_PROOF")["v232_route_decision_controller_report.json"]
    assert sess["route_state"] == "ROUTE_CONTROLLED_SESSION_REVIEW_READY"
    assert d["scale_applied"] is False and d["autonomous_trading_enabled"] is False
    assert_staged_safe(d)


# --- V233 completion scoreboard V3 ---
def test_v233_completion_scoreboard_v3_generated() -> None:
    d = generate_all_v233_reports_for_tests()["v233_completion_scoreboard_v3_controller_report.json"]
    assert d["completion_scoreboard_v3_controller_status"] == "PASS_COMPLETION_SCOREBOARD_V3_GENERATED"
    assert isinstance(d["fully_operational_estimate"], int)
    assert d["subsystem_percentages"]["architecture_governance"] == 100
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V234 acceleration lock + operator command sequence ---
def test_v234_acceleration_lock_default_await_intake() -> None:
    d = generate_all_v234_reports_for_tests()["v234_acceleration_lock_controller_report.json"]
    assert d["acceleration_lock_controller_status"] == "PASS_ACCELERATION_LOCK_AND_OPERATOR_COMMAND_SEQUENCE_READY"
    assert d["next_action_matrix_selection"] == "PROVIDE_EXTERNAL_AUTHORITY_INTAKE"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["operator_command_sequence"]
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    armed = generate_all_v234_reports_for_tests(intake_override=True, arming_override=True)["v234_acceleration_lock_controller_report.json"]
    assert armed["next_action_matrix_selection"] == "RUN_LIVE_PROOF_EXECUTE_ONCE"
    assert_staged_safe(d)


# --- safety / locks / no-runtime-approvals default across the whole bundle ---
def test_v225_to_v234_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v225_reports_for_tests,
        generate_all_v226_reports_for_tests,
        generate_all_v227_reports_for_tests,
        generate_all_v228_reports_for_tests,
        generate_all_v229_reports_for_tests,
        generate_all_v230_reports_for_tests,
        generate_all_v231_reports_for_tests,
        generate_all_v232_reports_for_tests,
        generate_all_v233_reports_for_tests,
        generate_all_v234_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
            assert report.get("runtime_approvals_created_by_dummy") is False
            assert report.get("approval_files_written", 0) == 0
            assert report.get("real_live_orders_submitted_count", 0) == 0
            assert report.get("real_broker_contacted") is False
            assert report.get("scale_applied") is False
            assert report.get("autonomous_trading_enabled") is False


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v225_reports_for_tests, generate_all_v228_reports_for_tests, generate_all_v230_reports_for_tests):
        gen()
    existed_after = (ROOT / "runtime" / "approvals").exists()
    # Dummy must not create the directory. If it pre-existed (operator-managed), that's unchanged.
    assert existed_after == existed_before
