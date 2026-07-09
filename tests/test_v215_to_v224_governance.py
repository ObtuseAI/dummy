from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v215_reports import generate_all_v215_reports_for_tests
from scripts.generate_v216_reports import generate_all_v216_reports_for_tests
from scripts.generate_v217_reports import generate_all_v217_reports_for_tests
from scripts.generate_v218_reports import generate_all_v218_reports_for_tests
from scripts.generate_v219_reports import generate_all_v219_reports_for_tests
from scripts.generate_v220_reports import generate_all_v220_reports_for_tests
from scripts.generate_v221_reports import generate_all_v221_reports_for_tests
from scripts.generate_v222_reports import generate_all_v222_reports_for_tests
from scripts.generate_v223_reports import generate_all_v223_reports_for_tests
from scripts.generate_v224_reports import generate_all_v224_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


# --- V215 operator activation packet (read-only, always PASS) ---
def test_v215_operator_activation_packet_ready_readonly() -> None:
    d = generate_all_v215_reports_for_tests()["v215_operator_activation_packet_controller_report.json"]
    assert d["operator_activation_packet_controller_status"] == "PASS_OPERATOR_ACTIVATION_PACKET_READY_READONLY"
    assert d["approval_files_written"] == 0
    assert d["total_real_live_orders_submitted"] == 0 and d["real_broker_contacted"] is False
    assert d["operator_checklist"] and d["first_live_proof_command_sequence"]
    assert_staged_safe(d)


# --- V216 external authority manifest intake (validate only) ---
def test_v216_default_absent_and_fixture_valid_no_write() -> None:
    d = generate_all_v216_reports_for_tests()["v216_external_authority_manifest_intake_controller_report.json"]
    assert d["external_authority_manifest_intake_controller_status"] == "PARTIAL_EXTERNAL_AUTHORITY_MANIFEST_ABSENT_OR_INCOMPLETE"
    assert d["approval_files_written"] == 0 and d["manifest_valid"] is False
    ok = generate_all_v216_reports_for_tests(manifest_approval=pilot_approval())["v216_external_authority_manifest_intake_controller_report.json"]
    assert ok["external_authority_manifest_intake_controller_status"] == "PASS_EXTERNAL_AUTHORITY_MANIFEST_VALIDATED_NO_SUBMIT"
    assert ok["manifest_valid"] is True and ok["approval_files_written"] == 0
    fuzzy = generate_all_v216_reports_for_tests(manifest_approval=pilot_approval("bad"))["v216_external_authority_manifest_intake_controller_report.json"]
    assert fuzzy["external_authority_manifest_intake_controller_status"] == "FAIL_CLOSED_EXTERNAL_AUTHORITY_MANIFEST_REJECTED"
    # hash-only ledger: raw phrase never serialized
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("manifest_approval_hash", ""))
    assert_staged_safe(ok)


# --- V217 zero-broker dry validation (always PASS, no contact) ---
def test_v217_zero_broker_dry_validation_complete() -> None:
    d = generate_all_v217_reports_for_tests()["v217_zero_broker_dry_validation_controller_report.json"]
    assert d["zero_broker_dry_validation_controller_status"] == "PASS_ZERO_BROKER_DRY_VALIDATION_COMPLETE"
    assert d["broker_contacted"] is False and d["firewall_submit_invoked"] is False
    assert d["dry_mode"] is True and d["live_orders"] == 0
    assert_staged_safe(d)


# --- V218 final live-proof arming check (no submit) ---
def test_v218_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v218_reports_for_tests()["v218_final_live_proof_arming_check_controller_report.json"]
    assert d["final_live_proof_arming_check_controller_status"] == "PARTIAL_FINAL_LIVE_PROOF_ARMING_BLOCKED"
    assert d["arming_ready"] is False and d["live_orders"] == 0
    ok = generate_all_v218_reports_for_tests(arming_override=True)["v218_final_live_proof_arming_check_controller_report.json"]
    assert ok["final_live_proof_arming_check_controller_status"] == "PASS_FINAL_LIVE_PROOF_ARMING_READY_NO_SUBMIT"
    assert ok["arming_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V219 hardened live-proof execution harness (only fire surface) ---
def test_v219_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v219_reports_for_tests()["v219_hardened_live_proof_execution_harness_controller_report.json"]
    assert d["hardened_live_proof_execution_harness_controller_status"] == "PARTIAL_HARDENED_LIVE_PROOF_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v219_reports_for_tests(
        proof_approval=pilot_approval(), arming_override=True, armable_override=True, env_gate_mode=True,
        env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF",
        live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v219-attempt-1"),
    )["v219_hardened_live_proof_execution_harness_controller_report.json"]
    assert c["hardened_live_proof_execution_harness_controller_status"] == "PASS_HARDENED_LIVE_PROOF_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v219-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v219_blocks_missing_env_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), arming_override=True, armable_override=True, env_gate_mode=True,
                env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, live_submit_operator_enabled=True,
                caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v219_hardened_live_proof_execution_harness_controller_report.json"
    no_env = generate_all_v219_reports_for_tests(**{**base, "env_gate_mode": False})[ctrl]
    assert no_env["firewall_submit_invoked"] is False and no_env["live_orders"] == 0
    no_arm = generate_all_v219_reports_for_tests(**{**base, "arming_override": False})[ctrl]
    assert no_arm["firewall_submit_invoked"] is False
    no_auth = generate_all_v219_reports_for_tests(**{**base, "armable_override": False})[ctrl]
    assert no_auth["firewall_submit_invoked"] is False
    fuzzy = generate_all_v219_reports_for_tests(**{**base, "proof_approval": pilot_approval("bad")})[ctrl]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v219_reports_for_tests(**{**base, "firewall_adapter": None})[ctrl]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V220 reconcile spine V2 ---
def test_v220_default_partial_and_override_classified() -> None:
    d = generate_all_v220_reports_for_tests()["v220_reconcile_spine_v2_controller_report.json"]
    assert d["reconcile_spine_v2_controller_status"] == "PARTIAL_NO_HARDENED_LIVE_PROOF_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v220_reports_for_tests(
        v219_final_override={"hardened_live_proof_execution_harness_controller_status": "PASS_HARDENED_LIVE_PROOF_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"},
        outcome_state="FILLED")["v220_reconcile_spine_v2_controller_report.json"]
    assert r["reconcile_spine_v2_controller_status"] == "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V221 forensic spine V2 ---
def test_v221_default_partial_and_override_reviewed() -> None:
    d = generate_all_v221_reports_for_tests()["v221_forensic_spine_v2_controller_report.json"]
    assert d["forensic_spine_v2_controller_status"] == "PARTIAL_NO_HARDENED_LIVE_PROOF_TO_FORENSIC_REVIEW"
    r = generate_all_v221_reports_for_tests(
        v220_final_override={"reconcile_spine_v2_controller_status": "PASS_RECONCILE_SPINE_V2_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED", "proof_target": "FIRST_REAL_PILOT_PROOF"})["v221_forensic_spine_v2_controller_report.json"]
    assert r["forensic_spine_v2_controller_status"] == "PASS_FORENSIC_SPINE_V2_REVIEWED_LOCKED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V222 repeat / controlled session bridge V2 ---
def test_v222_default_blocked_and_fixture_routed() -> None:
    d = generate_all_v222_reports_for_tests()["v222_repeat_controlled_session_bridge_v2_controller_report.json"]
    assert d["route_state"] == "ROUTE_BLOCKED_NO_LIVE_PROOF"
    ok = generate_all_v222_reports_for_tests(first_proof_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF")["v222_repeat_controlled_session_bridge_v2_controller_report.json"]
    assert ok["repeat_controlled_session_bridge_v2_controller_status"] == "PASS_REPEAT_CONTROLLED_SESSION_BRIDGE_V2_READY_LOCKED"
    assert ok["route_state"] == "ROUTE_REPEAT_PILOT_REVIEW_READY"
    sess = generate_all_v222_reports_for_tests(first_proof_override=True, proof_target_override="CONTROLLED_SESSION_PROOF")["v222_repeat_controlled_session_bridge_v2_controller_report.json"]
    assert sess["route_state"] == "ROUTE_CONTROLLED_SESSION_REVIEW_READY"
    assert d["scale_applied"] is False and d["autonomous_trading_enabled"] is False
    assert_staged_safe(d)


# --- V223 completion scoreboard V2 ---
def test_v223_completion_scoreboard_v2_generated() -> None:
    d = generate_all_v223_reports_for_tests()["v223_completion_scoreboard_v2_controller_report.json"]
    assert d["completion_scoreboard_v2_controller_status"] == "PASS_COMPLETION_SCOREBOARD_V2_GENERATED"
    assert isinstance(d["fully_operational_estimate"], int)
    assert d["subsystem_percentages"]["architecture_governance"] == 100
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V224 activation completion lock V2 ---
def test_v224_activation_completion_locked_default_await_manifest() -> None:
    d = generate_all_v224_reports_for_tests()["v224_activation_completion_lock_v2_controller_report.json"]
    assert d["activation_completion_lock_v2_controller_status"] == "PASS_ACTIVATION_COMPLETION_LOCKED"
    assert d["next_action_matrix_selection"] == "PROVIDE_EXTERNAL_AUTHORITY_MANIFEST"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    armed = generate_all_v224_reports_for_tests(manifest_override=True, arming_override=True)["v224_activation_completion_lock_v2_controller_report.json"]
    assert armed["next_action_matrix_selection"] == "RUN_HARDENED_LIVE_PROOF"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v215_to_v224_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v215_reports_for_tests,
        generate_all_v216_reports_for_tests,
        generate_all_v217_reports_for_tests,
        generate_all_v218_reports_for_tests,
        generate_all_v219_reports_for_tests,
        generate_all_v220_reports_for_tests,
        generate_all_v221_reports_for_tests,
        generate_all_v222_reports_for_tests,
        generate_all_v223_reports_for_tests,
        generate_all_v224_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
