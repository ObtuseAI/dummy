from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v205_reports_for_tests
from predator_mesh.report_runtime import generate_all_v206_reports_for_tests
from predator_mesh.report_runtime import generate_all_v207_reports_for_tests
from predator_mesh.report_runtime import generate_all_v208_reports_for_tests
from predator_mesh.report_runtime import generate_all_v209_reports_for_tests
from predator_mesh.report_runtime import generate_all_v210_reports_for_tests
from predator_mesh.report_runtime import generate_all_v211_reports_for_tests
from predator_mesh.report_runtime import generate_all_v212_reports_for_tests
from predator_mesh.report_runtime import generate_all_v213_reports_for_tests
from predator_mesh.report_runtime import generate_all_v214_reports_for_tests
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


def session_approval(phrase: str = sgc.CONTROLLED_SESSION_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled live session canary via firewall", "scope": sgc.CONTROLLED_SESSION_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "per_order_fail_closed_acknowledgment": "per-order fail-closed checks",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "session_auto_lock_acknowledgment": "immediate session auto-lock",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


# --- V205 completion baseline dedup ---
def test_v205_completion_baseline_deduped() -> None:
    d = generate_all_v205_reports_for_tests()["v205_completion_baseline_controller_report.json"]
    assert d["completion_baseline_controller_status"] == "PASS_COMPLETION_BASELINE_DEDUPED"
    assert d["remaining_blocker_count"] == 10
    assert d["total_live_orders"] == 0 and d["broker_contacted"] is False
    assert_staged_safe(d)


# --- V206 activation manifest linter ---
def test_v206_default_absent_and_fixture_valid_no_write() -> None:
    d = generate_all_v206_reports_for_tests()["v206_activation_manifest_controller_report.json"]
    assert d["activation_manifest_controller_status"] == "PARTIAL_ACTIVATION_MANIFEST_INPUTS_ABSENT"
    assert d["approval_files_written"] == 0
    ok = generate_all_v206_reports_for_tests(pilot_approval=pilot_approval())["v206_activation_manifest_controller_report.json"]
    assert ok["activation_manifest_controller_status"] == "PASS_ACTIVATION_MANIFEST_LINTED_VALID"
    fuzzy = generate_all_v206_reports_for_tests(pilot_approval=pilot_approval("bad"))["v206_activation_manifest_controller_report.json"]
    assert fuzzy["activation_manifest_controller_status"] == "FAIL_CLOSED_INVALID_MANIFEST_APPROVAL"
    assert_staged_safe(ok)


# --- V207 activation cockpit ---
def test_v207_cockpit_ready_readonly() -> None:
    d = generate_all_v207_reports_for_tests()["v207_activation_cockpit_report.json"]
    assert d["cockpit_controller_status"] == "PASS_ACTIVATION_COCKPIT_READY_READONLY"
    assert d["ui_submit_enabled"] is False and d["ui_config_write_enabled"] is False
    assert d["safe_mode"] == "READ_ONLY_FAIL_CLOSED"
    assert_staged_safe(d)


# --- V208 authority resolver ---
def test_v208_default_blocked_and_fixture_armable() -> None:
    d = generate_all_v208_reports_for_tests()["v208_authority_resolver_controller_report.json"]
    assert d["authority_state"] in ("DRY_LOCKED", "LIVE_BLOCKED_AUTHORITY_ABSENT")
    assert d["armable"] is False
    ok = generate_all_v208_reports_for_tests(approval_ok_override=True, config_ok_override=True, firewall_ok_override=True)["v208_authority_resolver_controller_report.json"]
    assert ok["authority_resolver_controller_status"] == "PASS_AUTHORITY_RESOLVER_LIVE_PROOF_ARMABLE_NO_SUBMIT"
    assert ok["authority_state"] == "LIVE_PROOF_ARMABLE"
    assert_staged_safe(ok)


# --- V209 live-proof runner wrapper ---
def test_v209_default_dry_not_armed_and_full_auth_double() -> None:
    d = generate_all_v209_reports_for_tests()["v209_live_proof_runner_controller_report.json"]
    assert d["live_proof_runner_controller_status"] == "PARTIAL_LIVE_PROOF_RUNNER_NOT_ARMED"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v209_reports_for_tests(proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v209-attempt-1"))["v209_live_proof_runner_controller_report.json"]
    assert c["live_proof_runner_controller_status"] == "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v209-attempt-1"
    assert c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v209_env_gate_authority_fuzzy_and_no_adapter_block() -> None:
    no_env = generate_all_v209_reports_for_tests(proof_approval=pilot_approval(), armable_override=True, env_gate_mode=False, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v209_live_proof_runner_controller_report.json"]
    assert no_env["firewall_submit_invoked"] is False
    no_auth = generate_all_v209_reports_for_tests(proof_approval=pilot_approval(), armable_override=False, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v209_live_proof_runner_controller_report.json"]
    assert no_auth["firewall_submit_invoked"] is False
    fuzzy = generate_all_v209_reports_for_tests(proof_approval=pilot_approval("bad"), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v209_live_proof_runner_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v209_reports_for_tests(proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v209_live_proof_runner_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V210 reconcile runner ---
def test_v210_default_partial_and_override_classified() -> None:
    d = generate_all_v210_reports_for_tests()["v210_reconcile_runner_controller_report.json"]
    assert d["reconcile_runner_controller_status"] == "PARTIAL_NO_LIVE_PROOF_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v210_reports_for_tests(v209_final_override={"live_proof_runner_controller_status": "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"}, outcome_state="FILLED")["v210_reconcile_runner_controller_report.json"]
    assert r["reconcile_runner_controller_status"] == "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V211 forensic runner ---
def test_v211_default_partial_and_override_reviewed() -> None:
    d = generate_all_v211_reports_for_tests()["v211_forensic_runner_controller_report.json"]
    assert d["forensic_runner_controller_status"] == "PARTIAL_NO_LIVE_PROOF_TO_FORENSIC_REVIEW"
    r = generate_all_v211_reports_for_tests(v210_final_override={"reconcile_runner_controller_status": "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED"})["v211_forensic_runner_controller_report.json"]
    assert r["forensic_runner_controller_status"] == "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V212 repeat/session bridge ---
def test_v212_default_blocked_and_fixture_routed() -> None:
    d = generate_all_v212_reports_for_tests()["v212_bridge_controller_report.json"]
    assert d["route_state"] == "ROUTE_BLOCKED_NO_LIVE_PROOF"
    ok = generate_all_v212_reports_for_tests(first_proof_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF")["v212_bridge_controller_report.json"]
    assert ok["bridge_controller_status"] == "PASS_REPEAT_SESSION_BRIDGE_READY_LOCKED"
    assert ok["route_state"] == "ROUTE_REPEAT_PILOT_REVIEW_READY"
    sess = generate_all_v212_reports_for_tests(first_proof_override=True, proof_target_override="CONTROLLED_SESSION_PROOF")["v212_bridge_controller_report.json"]
    assert sess["route_state"] == "ROUTE_CONTROLLED_SESSION_REVIEW_READY"
    assert_staged_safe(d)


# --- V213 completion scoreboard ---
def test_v213_completion_scoreboard_generated() -> None:
    d = generate_all_v213_reports_for_tests()["v213_completion_scoreboard_controller_report.json"]
    assert d["completion_scoreboard_controller_status"] == "PASS_COMPLETION_SCOREBOARD_GENERATED"
    assert isinstance(d["fully_operational_estimate"], int)
    assert d["subsystem_percentages"]["architecture_governance"] == 100
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V214 completion accelerator lock ---
def test_v214_accelerator_locked_default_await_approval_files() -> None:
    d = generate_all_v214_reports_for_tests()["v214_completion_accelerator_lock_controller_report.json"]
    assert d["completion_accelerator_lock_controller_status"] == "PASS_COMPLETION_ACCELERATOR_LOCKED"
    assert d["next_action_matrix_selection"] == "OPERATOR_PROVIDE_APPROVAL_FILES"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    armed = generate_all_v214_reports_for_tests(armable_override=True)["v214_completion_accelerator_lock_controller_report.json"]
    assert armed["next_action_matrix_selection"] == "RUN_FIRST_LIVE_PROOF"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v205_to_v214_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v205_reports_for_tests,
        generate_all_v206_reports_for_tests,
        generate_all_v207_reports_for_tests,
        generate_all_v208_reports_for_tests,
        generate_all_v209_reports_for_tests,
        generate_all_v210_reports_for_tests,
        generate_all_v211_reports_for_tests,
        generate_all_v212_reports_for_tests,
        generate_all_v213_reports_for_tests,
        generate_all_v214_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
