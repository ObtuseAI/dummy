from __future__ import annotations

from scripts.generate_v71_reports import generate_all_v71_reports_for_tests
from scripts.generate_v72_reports import generate_all_v72_reports_for_tests
from scripts.generate_v73_reports import generate_all_v73_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

SUBMITTED_V70_FINAL = {"live_canary_controller_status": "PASS_LIVE_CANARY_SUBMITTED", "simulated_canary_submits_count": 1, "verdict": "PASS"}


def test_v71_default_no_canary_to_reconcile() -> None:
    reports = generate_all_v71_reports_for_tests()
    controller = reports["v71_reconcile_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v70_baseline_status"] == "PASS_V70_BASELINE_READBACK"
    assert controller["reconcile_controller_status"] == "PARTIAL_NO_LIVE_CANARY_TO_RECONCILE"
    assert controller["further_submit_locked"] is True
    assert controller["real_live_orders_submitted_count"] == 0
    assert reports["final_report_v71.json"]["verdict"] == "PARTIAL"


def test_v71_reconciles_when_canary_submitted() -> None:
    reports = generate_all_v71_reports_for_tests(v70_final_override=SUBMITTED_V70_FINAL, outcome_state="FILLED")
    controller = reports["v71_reconcile_controller_report.json"]
    assert controller["reconcile_controller_status"] == "PASS_LIVE_CANARY_RECONCILED"
    assert controller["outcome_state"] == "FILLED"
    assert controller["no_repeat_submit_proof_status"] == "PASS_NO_REPEAT_SUBMIT"
    assert controller["auto_lock_after_outcome_status"] == "PASS_AUTO_LOCKED_AFTER_OUTCOME"
    assert reports["final_report_v71.json"]["verdict"] == "PASS"
    assert_staged_safe(controller)


def test_v72_risk_review_complete_and_locked() -> None:
    reports = generate_all_v72_reports_for_tests()
    controller = reports["v72_risk_governor_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v71_baseline_status"] == "PASS_V71_BASELINE_READBACK"
    assert controller["risk_governor_controller_status"] == "PASS_POST_TRADE_RISK_REVIEW_COMPLETE_LOCKED"
    assert controller["kill_switch_verification_status"] == "PASS_KILL_SWITCH_VERIFIED"
    assert controller["session_lock_verification_status"] == "PASS_SESSION_LOCKED"
    assert controller["live_submit_caps_unchanged_proof_status"] == "PASS_LIVE_SUBMIT_CAPS_UNCHANGED"
    assert controller["new_live_order_placed"] is False
    assert reports["final_report_v72.json"]["verdict"] == "PASS"


def test_v73_second_canary_gate_blocked_by_default_no_submit() -> None:
    reports = generate_all_v73_reports_for_tests()
    controller = reports["v73_second_canary_gate_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v72_baseline_status"] == "PASS_V72_BASELINE_READBACK"
    assert controller["second_canary_gate_controller_status"] == "PARTIAL_SECOND_CANARY_BLOCKED"
    assert controller["no_submit_proof_status"] == "PASS_NO_SUBMIT"
    assert controller["no_auto_scale_proof_status"] == "PASS_NO_AUTO_SCALE"
    assert controller["second_order_submitted"] is False
    assert "MISSING_V70_V71_FIRST_CANARY_PROOF" in reports["final_report_v73.json"]["current_blockers"]
    assert reports["final_report_v73.json"]["verdict"] == "PARTIAL"


def test_v71_v72_v73_safety_and_locks() -> None:
    for gen in (generate_all_v71_reports_for_tests, generate_all_v72_reports_for_tests, generate_all_v73_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
