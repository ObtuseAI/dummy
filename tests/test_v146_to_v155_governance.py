from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v146_reports import generate_all_v146_reports_for_tests
from archive.report_scripts.generate_v147_reports import generate_all_v147_reports_for_tests
from archive.report_scripts.generate_v148_reports import generate_all_v148_reports_for_tests
from archive.report_scripts.generate_v149_reports import generate_all_v149_reports_for_tests
from archive.report_scripts.generate_v150_reports import generate_all_v150_reports_for_tests
from archive.report_scripts.generate_v151_reports import generate_all_v151_reports_for_tests
from archive.report_scripts.generate_v152_reports import generate_all_v152_reports_for_tests
from archive.report_scripts.generate_v153_reports import generate_all_v153_reports_for_tests
from archive.report_scripts.generate_v154_reports import generate_all_v154_reports_for_tests
from archive.report_scripts.generate_v155_reports import generate_all_v155_reports_for_tests
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


def broker_readonly_approval(phrase: str = sgc.BROKER_READONLY_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "broker read-only verification only", "scope": sgc.BROKER_READONLY_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "pilot_id": order.get("pilot_id")}


# --- V146 operator handoff packet ---
def test_v146_handoff_ready_no_approval_write() -> None:
    d = generate_all_v146_reports_for_tests()["v146_handoff_controller_report.json"]
    assert d["handoff_controller_status"] == "PASS_OPERATOR_HANDOFF_PACKET_READY"
    assert d["approval_files_written"] == 0 and d["broker_contacted"] is False
    assert d["config_modified_by_dummy"] is False
    assert_staged_safe(d)


# --- V147 real authority intake validator ---
def test_v147_default_absent_and_fixture_valid_no_submit() -> None:
    d = generate_all_v147_reports_for_tests()["v147_intake_validator_controller_report.json"]
    assert d["intake_validator_controller_status"] == "PARTIAL_REAL_AUTHORITY_INPUTS_ABSENT_OR_INCOMPLETE"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    ok = generate_all_v147_reports_for_tests(pilot_approval=pilot_approval(), broker_readonly_approval=broker_readonly_approval(), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v147_intake_validator_controller_report.json"]
    assert ok["intake_validator_controller_status"] == "PASS_REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT"
    assert ok["broker_readonly_approval_validator_status"] == "PASS_BROKER_READONLY_APPROVAL_VALID"
    assert ok["approval_files_written"] == 0
    fuzzy = generate_all_v147_reports_for_tests(pilot_approval=pilot_approval("bad"), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v147_intake_validator_controller_report.json"]
    assert fuzzy["intake_validator_controller_status"] == "FAIL_CLOSED_INVALID_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V148 dry/live mode firewall ---
def test_v148_mode_firewall_locked_default_dry() -> None:
    d = generate_all_v148_reports_for_tests()["v148_mode_firewall_controller_report.json"]
    assert d["mode_firewall_controller_status"] == "PASS_MODE_FIREWALL_LOCKED"
    assert d["mode"] == "DRY_LOCKED" and d["live_mode"] == "LIVE_BLOCKED"
    live = generate_all_v148_reports_for_tests(live_authority_override=True)["v148_mode_firewall_controller_report.json"]
    assert live["mode"] == "LIVE_AUTHORIZED"
    assert_staged_safe(d)


# --- V149 rehearsal spine ---
def test_v149_rehearsal_spine_inert() -> None:
    d = generate_all_v149_reports_for_tests()["v149_rehearsal_controller_report.json"]
    assert d["rehearsal_controller_status"] == "PASS_PRODUCTION_PILOT_REHEARSAL_SPINE_READY_INERT"
    assert d["broker_contacted"] is False and d["rehearsal_inert"] is True
    assert d["hypothetical_order_summary"]["executable"] is False
    assert_staged_safe(d)


# --- V150 real pilot preflight packet ---
def test_v150_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v150_reports_for_tests()["v150_preflight_controller_report.json"]
    assert d["preflight_controller_status"] == "PARTIAL_REAL_PILOT_PREFLIGHT_BLOCKED"
    ok = generate_all_v150_reports_for_tests(intake_ready_override=True, mode_live_override=True, rehearsal_ready_override=True)["v150_preflight_controller_report.json"]
    assert ok["preflight_controller_status"] == "PASS_REAL_PILOT_PREFLIGHT_READY_NO_SUBMIT"
    assert ok["preflight_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V151 real pilot fire gate ---
def test_v151_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v151_reports_for_tests()["v151_real_pilot_gate_controller_report.json"]
    assert d["real_pilot_gate_controller_status"] == "PARTIAL_REAL_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v151_reports_for_tests(pilot_approval=pilot_approval(), preflight_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v151-attempt-1"))["v151_real_pilot_gate_controller_report.json"]
    assert c["real_pilot_gate_controller_status"] == "PASS_REAL_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v151-attempt-1"
    assert c["pilot_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v151_dry_mode_and_fuzzy_and_no_adapter_block() -> None:
    dry = generate_all_v151_reports_for_tests(pilot_approval=pilot_approval(), preflight_ready_override=True, mode_live_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v151_real_pilot_gate_controller_report.json"]
    assert dry["firewall_submit_invoked"] is False
    fuzzy = generate_all_v151_reports_for_tests(pilot_approval=pilot_approval("bad"), preflight_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v151_real_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v151_reports_for_tests(pilot_approval=pilot_approval(), preflight_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v151_real_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V152 reconcile intake ---
def test_v152_default_partial_and_override_classified() -> None:
    d = generate_all_v152_reports_for_tests()["v152_reconcile_intake_controller_report.json"]
    assert d["reconcile_intake_controller_status"] == "PARTIAL_NO_REAL_PILOT_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v152_reports_for_tests(v151_final_override={"real_pilot_gate_controller_status": "PASS_REAL_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1}, outcome_state="FILLED")["v152_reconcile_intake_controller_report.json"]
    assert r["reconcile_intake_controller_status"] == "PASS_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V153 forensic review ---
def test_v153_default_partial_and_override_reviewed() -> None:
    d = generate_all_v153_reports_for_tests()["v153_forensic_controller_report.json"]
    assert d["forensic_controller_status"] == "PARTIAL_NO_REAL_PILOT_TO_REVIEW"
    r = generate_all_v153_reports_for_tests(v152_final_override={"reconcile_intake_controller_status": "PASS_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED"})["v153_forensic_controller_report.json"]
    assert r["forensic_controller_status"] == "PASS_REAL_PILOT_FORENSIC_REVIEWED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V154 repeat pilot preflight lock ---
def test_v154_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v154_reports_for_tests()["v154_repeat_preflight_controller_report.json"]
    assert d["repeat_preflight_controller_status"] == "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"
    ok = generate_all_v154_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True)["v154_repeat_preflight_controller_report.json"]
    assert ok["repeat_preflight_controller_status"] == "PASS_REPEAT_PREFLIGHT_READY_LOCKED"
    assert ok["repeat_preflight_ready"] is True and ok["live_orders"] == 0
    fuzzy = generate_all_v154_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True)["v154_repeat_preflight_controller_report.json"]
    assert fuzzy["repeat_preflight_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V155 controlled operation lock V3 ---
def test_v155_controlled_operation_lock_default_blocked_authority() -> None:
    d = generate_all_v155_reports_for_tests()["v155_controlled_operation_lock_controller_report.json"]
    assert d["controlled_operation_lock_controller_status"] == "PASS_CONTROLLED_OPERATION_LOCK_SUMMARY_GENERATED"
    assert d["controlled_operation_status"] == "CONTROLLED_OPERATION_BLOCKED_AUTHORITY_ABSENT"
    assert d["next_action_matrix_selection"] == "AWAIT_REAL_PILOT_APPROVAL"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v155_reports_for_tests(authority_ready_override=True, pilot_done_override=True, reconcile_done_override=False)["v155_controlled_operation_lock_controller_report.json"]
    assert ready["controlled_operation_status"] == "CONTROLLED_OPERATION_BLOCKED_RECONCILE_ABSENT"
    assert ready["next_action_matrix_selection"] == "AWAIT_REAL_PILOT_RECONCILE"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v146_to_v155_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v146_reports_for_tests,
        generate_all_v147_reports_for_tests,
        generate_all_v148_reports_for_tests,
        generate_all_v149_reports_for_tests,
        generate_all_v150_reports_for_tests,
        generate_all_v151_reports_for_tests,
        generate_all_v152_reports_for_tests,
        generate_all_v153_reports_for_tests,
        generate_all_v154_reports_for_tests,
        generate_all_v155_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
