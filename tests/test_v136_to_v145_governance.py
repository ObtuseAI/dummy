from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v136_reports_for_tests
from predator_mesh.report_runtime import generate_all_v137_reports_for_tests
from predator_mesh.report_runtime import generate_all_v138_reports_for_tests
from predator_mesh.report_runtime import generate_all_v139_reports_for_tests
from predator_mesh.report_runtime import generate_all_v140_reports_for_tests
from predator_mesh.report_runtime import generate_all_v141_reports_for_tests
from predator_mesh.report_runtime import generate_all_v142_reports_for_tests
from predator_mesh.report_runtime import generate_all_v143_reports_for_tests
from predator_mesh.report_runtime import generate_all_v144_reports_for_tests
from predator_mesh.report_runtime import generate_all_v145_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


def repeat_approval(phrase: str = sgc.REPEAT_PILOT_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review a repeat controlled production pilot only", "scope": sgc.REPEAT_PILOT_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "pilot_id": order.get("pilot_id"), "repeat_pilot_id": order.get("repeat_pilot_id")}


# --- V136 authority binder ---
def test_v136_default_incomplete_and_fixture_bound() -> None:
    d = generate_all_v136_reports_for_tests()["v136_authority_binder_controller_report.json"]
    assert d["authority_binder_controller_status"] == "PARTIAL_PILOT_AUTHORITY_INCOMPLETE"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    ok = generate_all_v136_reports_for_tests(pilot_approval=pilot_approval(), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v136_authority_binder_controller_report.json"]
    assert ok["authority_binder_controller_status"] == "PASS_PILOT_AUTHORITY_BOUND_NO_SUBMIT"
    assert ok["authority_bound"] is True and ok["live_orders"] == 0
    fuzzy = generate_all_v136_reports_for_tests(pilot_approval=pilot_approval("bad"), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v136_authority_binder_controller_report.json"]
    assert fuzzy["authority_binder_controller_status"] == "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V137 live-submit/caps immutable snapshot ---
def test_v137_default_not_ready_and_fixture_snapshot() -> None:
    d = generate_all_v137_reports_for_tests()["v137_config_snapshot_controller_report.json"]
    assert d["config_snapshot_controller_status"] == "PARTIAL_LIVE_SUBMIT_OR_CAPS_NOT_READY"
    assert d["caps_changed"] is False and d["live_submit_changed"] is False
    ok = generate_all_v137_reports_for_tests(live_submit_operator_enabled=True, caps_config_present=True)["v137_config_snapshot_controller_report.json"]
    assert ok["config_snapshot_controller_status"] == "PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_READONLY"
    assert ok["caps_changed"] is False
    assert_staged_safe(d)


# --- V138 firewall adapter contract ---
def test_v138_default_absent_and_fixture_verified() -> None:
    d = generate_all_v138_reports_for_tests()["v138_firewall_adapter_controller_report.json"]
    assert d["firewall_adapter_controller_status"] == "PARTIAL_FIREWALL_ADAPTER_ABSENT"
    assert d["real_broker_contacted"] is False
    ok = generate_all_v138_reports_for_tests(firewall_adapter=FakeFirewall("x"))["v138_firewall_adapter_controller_report.json"]
    assert ok["firewall_adapter_controller_status"] == "PASS_FIREWALL_ADAPTER_CONTRACT_VERIFIED"
    assert ok["real_broker_contacted"] is False
    assert_staged_safe(ok)


# --- V139 candidate refresh / abstention preflight ---
def test_v139_candidate_preflight_pass_no_submit() -> None:
    d = generate_all_v139_reports_for_tests()["v139_candidate_preflight_controller_report.json"]
    assert d["candidate_preflight_controller_status"] == "PASS_CANDIDATE_ABSTENTION_PREFLIGHT_COMPLETE"
    assert d["abstention_decision"] == "TRADE_ELIGIBLE_REVIEW_ONLY"
    assert d["submit_enabled"] is False
    abstain = generate_all_v139_reports_for_tests(abstain_override=True)["v139_candidate_preflight_controller_report.json"]
    assert abstain["abstention_decision"] == "ABSTAIN_REQUIRED"
    assert_staged_safe(d)


# --- V140 final production pilot auth packet ---
def test_v140_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v140_reports_for_tests()["v140_final_auth_packet_controller_report.json"]
    assert d["final_auth_packet_controller_status"] == "PARTIAL_FINAL_PILOT_AUTH_PACKET_BLOCKED"
    ok = generate_all_v140_reports_for_tests(binder_ready_override=True, snapshot_ready_override=True, firewall_ready_override=True, candidate_ready_override=True)["v140_final_auth_packet_controller_report.json"]
    assert ok["final_auth_packet_controller_status"] == "PASS_FINAL_PILOT_AUTH_PACKET_READY_NO_SUBMIT"
    assert ok["auth_packet_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V141 controlled production pilot fire ---
def test_v141_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v141_reports_for_tests()["v141_pilot_gate_controller_report.json"]
    assert d["pilot_gate_controller_status"] == "PARTIAL_PRODUCTION_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v141_reports_for_tests(pilot_approval=pilot_approval(), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v141-attempt-1"))["v141_pilot_gate_controller_report.json"]
    assert c["pilot_gate_controller_status"] == "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v141-attempt-1"
    assert c["pilot_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v141_fuzzy_and_no_adapter_block() -> None:
    fuzzy = generate_all_v141_reports_for_tests(pilot_approval=pilot_approval("bad"), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v141_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v141_reports_for_tests(pilot_approval=pilot_approval(), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v141_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V142 pilot reconcile ---
def test_v142_default_partial_and_override_reconciled() -> None:
    d = generate_all_v142_reports_for_tests()["v142_pilot_reconcile_controller_report.json"]
    assert d["pilot_reconcile_controller_status"] == "PARTIAL_NO_PRODUCTION_PILOT_TO_RECONCILE"
    r = generate_all_v142_reports_for_tests(v141_final_override={"pilot_gate_controller_status": "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1})["v142_pilot_reconcile_controller_report.json"]
    assert r["pilot_reconcile_controller_status"] == "PASS_PRODUCTION_PILOT_RECONCILED_REVIEWED_AUTOLOCKED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V143 repeat pilot eligibility gate ---
def test_v143_default_absent_and_fixture_ready() -> None:
    d = generate_all_v143_reports_for_tests()["v143_repeat_eligibility_controller_report.json"]
    assert d["repeat_eligibility_controller_status"] == "PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT"
    ok = generate_all_v143_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True)["v143_repeat_eligibility_controller_report.json"]
    assert ok["repeat_eligibility_controller_status"] == "PASS_REPEAT_PILOT_REVIEW_READY_LOCKED"
    fuzzy = generate_all_v143_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True)["v143_repeat_eligibility_controller_report.json"]
    assert fuzzy["repeat_eligibility_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V144 repeat production pilot fire ---
def test_v144_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v144_reports_for_tests()["v144_repeat_pilot_gate_controller_report.json"]
    assert d["repeat_pilot_gate_controller_status"] == "PARTIAL_REPEAT_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v144_reports_for_tests(repeat_approval=repeat_approval(), repeat_ready_override=True, first_pilot_reviewed_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v144-attempt-1"))["v144_repeat_pilot_gate_controller_report.json"]
    assert c["repeat_pilot_gate_controller_status"] == "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v144-attempt-1"
    assert c["repeat_pilot_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["campaign_auto_started"] is False
    assert_staged_safe(c)


def test_v144_missing_first_pilot_and_fuzzy_block() -> None:
    no_first = generate_all_v144_reports_for_tests(repeat_approval=repeat_approval(), repeat_ready_override=True, first_pilot_reviewed_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v144_repeat_pilot_gate_controller_report.json"]
    assert no_first["firewall_submit_invoked"] is False
    fuzzy = generate_all_v144_reports_for_tests(repeat_approval=repeat_approval("bad"), repeat_ready_override=True, first_pilot_reviewed_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v144_repeat_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False and fuzzy["live_orders"] == 0


# --- V145 production pilot closeout ---
def test_v145_closeout_summary_default_await_pilot() -> None:
    d = generate_all_v145_reports_for_tests()["v145_closeout_controller_report.json"]
    assert d["closeout_controller_status"] == "PASS_PRODUCTION_PILOT_CLOSEOUT_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_PRODUCTION_PILOT_APPROVAL"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v145_reports_for_tests(pilot_override="PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", repeat_override="PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED", scale_override="SCALE_STEP_1_REVIEW_READY")["v145_closeout_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "CONTROLLED_OPERATION_READY_LOCKED"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v136_to_v145_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v136_reports_for_tests,
        generate_all_v137_reports_for_tests,
        generate_all_v138_reports_for_tests,
        generate_all_v139_reports_for_tests,
        generate_all_v140_reports_for_tests,
        generate_all_v141_reports_for_tests,
        generate_all_v142_reports_for_tests,
        generate_all_v143_reports_for_tests,
        generate_all_v144_reports_for_tests,
        generate_all_v145_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
