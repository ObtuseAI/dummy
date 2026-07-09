from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v77_reports import generate_all_v77_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def v70_packet(phrase: str = sgc.V70_LIVE_CANARY_SUBMIT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "arm and submit one tiny live limit canary via firewall", "scope": sgc.V70_LIVE_CANARY_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "max_one_order_acknowledgment": "exactly one order",
        "limit_only_acknowledgment": "limit only", "no_market_order_acknowledgment": "no market order",
        "firewall_only_acknowledgment": "firewall only", "rollback_acknowledgment": "immediate fail-closed rollback",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
    }


class FakeFirewall:
    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": "v77-attempt-1", "accepted": True, "real_broker_contacted": False, "market_order": False}


def test_v77_default_no_submit() -> None:
    reports = generate_all_v77_reports_for_tests()
    controller = reports["v77_live_canary_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["live_canary_controller_status"] == "PARTIAL_FIRST_CANARY_NOT_ARMED"
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["firewall_submit_invoked"] is False
    assert reports["final_report_v77.json"]["verdict"] == "PARTIAL"


def test_v77_fuzzy_approval_does_not_arm() -> None:
    controller = generate_all_v77_reports_for_tests(approval_input=v70_packet("I approve a live canary"), v76_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())["v77_live_canary_controller_report.json"]
    assert controller["live_canary_controller_status"] == "PARTIAL_FIRST_CANARY_NOT_ARMED"
    assert controller["firewall_submit_invoked"] is False
    assert controller["real_live_orders_submitted_count"] == 0


def test_v77_full_authority_injected_double_records_single_attempt_no_real_order() -> None:
    reports = generate_all_v77_reports_for_tests(approval_input=v70_packet(), v76_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())
    controller = reports["v77_live_canary_controller_report.json"]
    assert controller["live_canary_controller_status"] == "PASS_LIVE_CANARY_SUBMITTED"
    assert controller["firewall_submit_invoked"] is True
    assert controller["single_submit_locked"] is True
    assert controller["order_attempt_id"] == "v77-attempt-1"
    assert controller["current_next_action"] == "LIVE_CANARY_SUBMITTED_AWAIT_RECONCILE"
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["real_broker_contacted"] is False
    assert controller["market_order_submitted"] is False
    assert controller["dummy_enabled_live_submit"] is False
    assert controller["dummy_modified_caps"] is False
    assert reports["final_report_v77.json"]["verdict"] == "PASS"
    assert_staged_safe(controller)


def test_v77_no_adapter_even_with_approval_does_not_submit() -> None:
    controller = generate_all_v77_reports_for_tests(approval_input=v70_packet(), v76_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v77_live_canary_controller_report.json"]
    assert controller["firewall_submit_invoked"] is False
    assert controller["real_live_orders_submitted_count"] == 0
