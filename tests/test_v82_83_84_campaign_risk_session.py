from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v82_reports import generate_all_v82_reports_for_tests
from scripts.generate_v83_reports import generate_all_v83_reports_for_tests
from scripts.generate_v84_reports import generate_all_v84_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v82_campaign_gate_locked_no_auto_submit() -> None:
    reports = generate_all_v82_reports_for_tests()
    controller = reports["v82_campaign_gate_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v81_baseline_status"] == "PASS_V81_BASELINE_READBACK"
    assert controller["campaign_gate_controller_status"] == "PASS_MICRO_CAMPAIGN_GATE_READY_LOCKED"
    assert controller["per_order_approval_requirement_status"] == "PASS_PER_ORDER_APPROVAL_REQUIRED"
    assert controller["no_auto_submit_proof_status"] == "PASS_NO_AUTO_SUBMIT"
    assert controller["automatic_live_orders_enabled"] is False
    assert controller["campaign_live_orders_submitted"] == 0
    assert reports["final_report_v82.json"]["verdict"] == "PASS"


def test_v82_campaign_approval_is_separate_phrase() -> None:
    controller = generate_all_v82_reports_for_tests(campaign_approval={"exact_phrase": sgc.MICRO_CAMPAIGN_PHRASE})["v82_campaign_gate_controller_report.json"]
    assert controller["campaign_approval_validator_status"] == "PASS_CAMPAIGN_APPROVAL_PRESENT"
    # Even with campaign approval, no automatic live orders.
    assert controller["automatic_live_orders_enabled"] is False
    assert_staged_safe(controller)


def test_v83_risk_hardening_scaling_policy_no_live_order() -> None:
    reports = generate_all_v83_reports_for_tests()
    controller = reports["v83_risk_hardening_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["risk_hardening_controller_status"] == "PASS_RISK_HARDENED_SCALING_POLICY_LOCKED"
    assert controller["kill_switch_status"] == "PASS_POLICY_DEFINED"
    assert controller["scale_step_policy_status"] == "PASS_POLICY_DEFINED"
    assert controller["caps_modified_by_dummy"] is False
    assert controller["live_order_placed"] is False
    assert reports["final_report_v83.json"]["verdict"] == "PASS"


def test_v84_production_readiness_locked_no_autonomous_trading() -> None:
    reports = generate_all_v84_reports_for_tests()
    controller = reports["v84_session_governor_report.json"]
    assert_staged_safe(controller)
    assert controller["session_governor_status"] == "PASS_PRODUCTION_READINESS_AUDIT_LOCKED"
    assert controller["production_readiness_checklist_status"] == "PASS_PRODUCTION_READINESS_AUDIT_LOCKED"
    assert controller["autonomous_trading_enabled"] is False
    assert controller["production_readiness_checklist"]["autonomous_trading_enabled"] is False
    assert controller["per_order_approval_mode_status"] == "PASS_DEFINED_LOCKED"
    assert reports["final_report_v84.json"]["verdict"] == "PASS"


def test_v82_83_84_safety_and_locks() -> None:
    for gen in (generate_all_v82_reports_for_tests, generate_all_v83_reports_for_tests, generate_all_v84_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
