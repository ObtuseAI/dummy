from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v64_reports import generate_all_v64_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v64_preflight_validates_future_requirements_no_submit() -> None:
    reports = generate_all_v64_reports_for_tests()
    controller = reports["v64_firewall_preflight_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v63_baseline_status"] == "PASS_V63_BASELINE_READBACK"
    assert controller["firewall_preflight_controller_status"] == "PASS_FIREWALL_PREFLIGHT_ONLY_NO_SUBMIT"
    assert controller["limit_order_only_rule_validator_status"] == "PASS_LIMIT_ORDER_ONLY"
    assert controller["no_submit_call_validator_status"] == "PASS_NO_SUBMIT_CALL"
    assert controller["no_cancel_call_validator_status"] == "PASS_NO_CANCEL_CALL"
    assert controller["no_private_account_access_validator_status"] == "PASS_NO_PRIVATE_ACCOUNT_ACCESS"
    assert controller["caps_readonly_proof_status"] == "PASS_CAPS_READONLY"
    assert controller["live_submit_disabled_proof_status"] == "PASS_LIVE_SUBMIT_DISABLED"
    assert controller["kill_switch_requirement_validator_status"] == "PASS_KILL_SWITCH_REQUIRED"
    assert controller["rollback_requirement_validator_status"] == "PASS_ROLLBACK_REQUIRED"
    assert controller["idempotency_requirement_validator_status"] == "PASS_IDEMPOTENCY_REQUIRED"
    assert reports["final_report_v64.json"]["verdict"] == "PASS"


def test_v64_future_live_canary_phrase_not_accepted_here() -> None:
    controller = generate_all_v64_reports_for_tests()["v64_firewall_preflight_controller_report.json"]
    assert controller["future_live_canary_approval_phrase"] == sgc.LIVE_CANARY_PHRASE
    assert controller["future_live_canary_phrase_accepted_here"] is False


def test_v64_safety_and_locks() -> None:
    reports = generate_all_v64_reports_for_tests()
    for name, report in reports.items():
        if name == "final_report_v64.json":
            continue
        assert_staged_safe(report)
