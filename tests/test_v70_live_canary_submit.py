from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v70_reports import generate_all_v70_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def v70_packet(phrase: str = sgc.V70_LIVE_CANARY_SUBMIT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase,
        "operator": "operator:chris",
        "timestamp": "2026-07-05T21:00:00Z",
        "reason": "arm and submit one tiny live limit canary via firewall",
        "scope": sgc.V70_LIVE_CANARY_SCOPE,
        "expiration": "2026-07-06T21:00:00Z",
        "max_one_order_acknowledgment": "exactly one order",
        "limit_only_acknowledgment": "limit only",
        "no_market_order_acknowledgment": "no market order",
        "firewall_only_acknowledgment": "firewall only",
        "rollback_acknowledgment": "immediate fail-closed rollback",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
    }


class FakeFirewall:
    """Non-broker test double. Records a single gated attempt; contacts no real broker."""

    def submit(self, order):
        return {"order_attempt_id": "v70-attempt-1", "accepted": True, "real_broker_contacted": False, "live": False, "market_order": False}


def test_v70_default_no_submit_no_real_order() -> None:
    reports = generate_all_v70_reports_for_tests()
    controller = reports["v70_live_canary_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v69_baseline_status"] == "PASS_V69_BASELINE_READBACK"
    assert controller["live_canary_controller_status"] == "PARTIAL_LIVE_CANARY_NOT_ARMED"
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["firewall_submit_invoked"] is False
    assert reports["final_report_v70.json"]["verdict"] == "PARTIAL"


def test_v70_approval_without_adapter_or_config_does_not_submit() -> None:
    controller = generate_all_v70_reports_for_tests(approval_input=v70_packet())["v70_live_canary_controller_report.json"]
    assert controller["approval_validated"] is True
    assert controller["live_canary_controller_status"] == "PARTIAL_LIVE_CANARY_NOT_ARMED"
    assert controller["firewall_submit_invoked"] is False
    assert controller["real_live_orders_submitted_count"] == 0


def test_v70_fuzzy_approval_fails_closed_precheck() -> None:
    controller = generate_all_v70_reports_for_tests(approval_input=v70_packet("I approve submitting a live canary"))["v70_live_canary_controller_report.json"]
    assert controller["live_canary_controller_status"] == "FAIL_CLOSED_PRECHECK_FAILED"
    assert controller["firewall_submit_invoked"] is False
    assert controller["real_live_orders_submitted_count"] == 0


def test_v70_full_approval_with_injected_firewall_double_records_single_gated_attempt_no_real_order() -> None:
    reports = generate_all_v70_reports_for_tests(
        approval_input=v70_packet(),
        live_submit_operator_enabled=True,
        caps_config_present=True,
        firewall_adapter=FakeFirewall(),
    )
    controller = reports["v70_live_canary_controller_report.json"]
    assert controller["live_canary_controller_status"] == "PASS_LIVE_CANARY_SUBMITTED"
    assert controller["firewall_submit_invoked"] is True
    assert controller["single_submit_locked"] is True
    assert controller["post_submit_auto_lock_status"] == "PASS_POST_SUBMIT_AUTO_LOCKED"
    assert controller["order_attempt_id"] == "v70-attempt-1"
    assert controller["next_action" if "next_action" in controller else "current_next_action"] == "LIVE_CANARY_SUBMITTED_AWAIT_RECONCILE"
    # No REAL live order, no real broker, no market order, Dummy did not enable live-submit or caps.
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["real_broker_contacted"] is False
    assert controller["market_order_submitted"] is False
    assert controller["dummy_enabled_live_submit"] is False
    assert controller["dummy_modified_caps"] is False
    assert reports["final_report_v70.json"]["verdict"] == "PASS"
    assert_staged_safe(controller)


def test_v70_safety_and_locks_default() -> None:
    for name, report in generate_all_v70_reports_for_tests().items():
        if name == "final_report_v70.json":
            continue
        assert_staged_safe(report)
