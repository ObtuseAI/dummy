from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v126_reports import generate_all_v126_reports_for_tests
from scripts.generate_v127_reports import generate_all_v127_reports_for_tests
from scripts.generate_v128_reports import generate_all_v128_reports_for_tests
from scripts.generate_v129_reports import generate_all_v129_reports_for_tests
from scripts.generate_v130_reports import generate_all_v130_reports_for_tests
from scripts.generate_v131_reports import generate_all_v131_reports_for_tests
from scripts.generate_v132_reports import generate_all_v132_reports_for_tests
from scripts.generate_v133_reports import generate_all_v133_reports_for_tests
from scripts.generate_v134_reports import generate_all_v134_reports_for_tests
from scripts.generate_v135_reports import generate_all_v135_reports_for_tests
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


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def operation_approval(phrase: str = sgc.CONTROLLED_OPERATION_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review controlled operation eligibility only", "scope": sgc.CONTROLLED_OPERATION_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "pilot_id": order.get("pilot_id")}


# --- V126 pilot blocker closure / authority map ---
def test_v126_pilot_blockers_audited_authority_mapped() -> None:
    d = generate_all_v126_reports_for_tests()["v126_pilot_blocker_controller_report.json"]
    assert d["pilot_blocker_controller_status"] == "PASS_PILOT_BLOCKERS_AUDITED_AUTHORITY_MAPPED"
    assert d["next_action_matrix_selection"] == "AWAIT_CONTROLLED_PILOT_AUTHORITY"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    assert_staged_safe(d)


# --- V127 pilot approval/config/caps/firewall tieout ---
def test_v127_default_absent_and_fixture_tieout_ready_no_submit() -> None:
    d = generate_all_v127_reports_for_tests()["v127_pilot_tieout_controller_report.json"]
    assert d["pilot_tieout_controller_status"] == "PARTIAL_PILOT_APPROVAL_OR_CONFIG_ABSENT"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    ok = generate_all_v127_reports_for_tests(pilot_approval=pilot_approval(), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v127-x"))["v127_pilot_tieout_controller_report.json"]
    assert ok["pilot_tieout_controller_status"] == "PASS_PILOT_APPROVAL_CONFIG_FIREWALL_TIEOUT_READY_NO_SUBMIT"
    assert ok["tieout_ready"] is True and ok["live_orders"] == 0
    fuzzy = generate_all_v127_reports_for_tests(pilot_approval=pilot_approval("bad"), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v127_pilot_tieout_controller_report.json"]
    assert fuzzy["pilot_tieout_controller_status"] == "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V128 pilot final authorization packet ---
def test_v128_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v128_reports_for_tests()["v128_pilot_auth_packet_controller_report.json"]
    assert d["pilot_auth_packet_controller_status"] == "PARTIAL_PILOT_AUTH_PACKET_BLOCKED"
    ok = generate_all_v128_reports_for_tests(tieout_ready_override=True, risk_ready_override=True, gate_ready_override=True)["v128_pilot_auth_packet_controller_report.json"]
    assert ok["pilot_auth_packet_controller_status"] == "PASS_PRODUCTION_PILOT_AUTH_PACKET_READY_NO_SUBMIT"
    assert ok["auth_packet_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V129 controlled production pilot fire on full auth ---
def test_v129_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v129_reports_for_tests()["v129_pilot_gate_controller_report.json"]
    assert d["pilot_gate_controller_status"] == "PARTIAL_PRODUCTION_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v129_reports_for_tests(pilot_approval=pilot_approval(), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v129-attempt-1"))["v129_pilot_gate_controller_report.json"]
    assert c["pilot_gate_controller_status"] == "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v129-attempt-1"
    assert c["pilot_locked"] is True
    assert c["live_orders"] == 0
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v129_fuzzy_and_no_adapter_block() -> None:
    fuzzy = generate_all_v129_reports_for_tests(pilot_approval=pilot_approval("bad"), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v129_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v129_reports_for_tests(pilot_approval=pilot_approval(), auth_packet_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v129_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False
    assert no_adapter["live_orders"] == 0


# --- V130 pilot reconcile / forensic review ---
def test_v130_default_partial_and_override_reconciled() -> None:
    d = generate_all_v130_reports_for_tests()["v130_pilot_reconcile_controller_report.json"]
    assert d["pilot_reconcile_controller_status"] == "PARTIAL_NO_PRODUCTION_PILOT_TO_RECONCILE"
    r = generate_all_v130_reports_for_tests(v129_final_override={"pilot_gate_controller_status": "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1})["v130_pilot_reconcile_controller_report.json"]
    assert r["pilot_reconcile_controller_status"] == "PASS_PRODUCTION_PILOT_RECONCILED_REVIEWED_AUTOLOCKED"
    assert r["pilot_forensic_capture"]["private_data_leaked"] is False
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V131 repeat pilot review gate ---
def test_v131_default_absent_and_fixture_review_ready() -> None:
    d = generate_all_v131_reports_for_tests()["v131_repeat_pilot_gate_controller_report.json"]
    assert d["repeat_pilot_gate_controller_status"] == "PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT"
    assert d["live_orders"] == 0 and d["auto_repeat_enabled"] is False
    ok = generate_all_v131_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True)["v131_repeat_pilot_gate_controller_report.json"]
    assert ok["repeat_pilot_gate_controller_status"] == "PASS_REPEAT_PILOT_REVIEW_READY_LOCKED"
    assert ok["repeat_pilot_recommendation"] == "REPEAT_PILOT_REVIEW_READY"
    fuzzy = generate_all_v131_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True)["v131_repeat_pilot_gate_controller_report.json"]
    assert fuzzy["repeat_pilot_gate_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V132 production risk stop policy V2 ---
def test_v132_risk_stop_policies_locked_no_order() -> None:
    d = generate_all_v132_reports_for_tests()["v132_risk_stop_policy_controller_report.json"]
    assert d["risk_stop_policy_controller_status"] == "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED"
    assert d["session_kill_switch_status"] == "PASS_SESSION_KILL_SWITCH_ARMED"
    assert d["caps_modified"] is False and d["live_orders"] == 0
    assert_staged_safe(d)


# --- V133 scale review V2 ---
def test_v133_scale_review_no_caps_change() -> None:
    d = generate_all_v133_reports_for_tests()["v133_scale_review_controller_report.json"]
    assert d["scale_review_controller_status"] == "PASS_SCALE_REVIEWED_NO_SCALE_APPLIED"
    assert d["scale_recommendation"] == "NO_SCALE"
    assert d["caps_changed"] is False and d["scale_applied"] is False
    ready = generate_all_v133_reports_for_tests(scale_approval=scale_approval(), pilot_evidence_override=True, production_ready_override=True)["v133_scale_review_controller_report.json"]
    assert ready["scale_recommendation"] == "SCALE_STEP_1_REVIEW_READY"
    fuzzy = generate_all_v133_reports_for_tests(scale_approval=scale_approval("bad"))["v133_scale_review_controller_report.json"]
    assert fuzzy["scale_review_controller_status"] == "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
    assert_staged_safe(ready)


# --- V134 controlled operation gate V2 ---
def test_v134_controlled_operation_ready_locked_no_autonomy() -> None:
    d = generate_all_v134_reports_for_tests()["v134_controlled_operation_gate_controller_report.json"]
    assert d["controlled_operation_gate_controller_status"] == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"
    assert d["autonomous_trading_enabled"] is False
    assert d["per_order_approval_required"] is True
    ok = generate_all_v134_reports_for_tests(operation_approval=operation_approval())["v134_controlled_operation_gate_controller_report.json"]
    assert ok["controlled_operation_review_validator_status"] == "PASS_CONTROLLED_OPERATION_REVIEW_VALID"
    assert ok["controlled_operation_gate_controller_status"] == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"
    assert_staged_safe(d)


# --- V135 production lock summary / next-phase map ---
def test_v135_production_lock_summary_default_await_pilot() -> None:
    d = generate_all_v135_reports_for_tests()["v135_production_lock_controller_report.json"]
    assert d["production_lock_controller_status"] == "PASS_PRODUCTION_LOCK_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_PRODUCTION_PILOT_APPROVAL"
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    assert d["new_order_placed"] is False
    ready = generate_all_v135_reports_for_tests(pilot_override="PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", repeat_override="PASS_REPEAT_PILOT_REVIEW_READY_LOCKED", scale_override="SCALE_STEP_1_REVIEW_READY")["v135_production_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "CONTROLLED_OPERATION_READY_LOCKED"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v126_to_v135_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v126_reports_for_tests,
        generate_all_v127_reports_for_tests,
        generate_all_v128_reports_for_tests,
        generate_all_v129_reports_for_tests,
        generate_all_v130_reports_for_tests,
        generate_all_v131_reports_for_tests,
        generate_all_v132_reports_for_tests,
        generate_all_v133_reports_for_tests,
        generate_all_v134_reports_for_tests,
        generate_all_v135_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
