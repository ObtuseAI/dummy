from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v66_reports import generate_all_v66_reports_for_tests
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


def test_v66_default_partial_without_live_canary_approval() -> None:
    reports = generate_all_v66_reports_for_tests()
    validator = reports["v66_approval_packet_validator_report.json"]
    assert_staged_safe(validator)
    assert validator["v65_baseline_status"] == "PASS_V65_BASELINE_READBACK"
    assert validator["approval_packet_validator_status"] == "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"
    assert validator["live_submit_config_readonly_checker_status"] == "PASS_LIVE_SUBMIT_READ_ONLY"
    assert validator["caps_config_readonly_checker_status"] == "PASS_CAPS_READ_ONLY"
    assert validator["dummy_enabled_live_submit"] is False
    assert validator["dummy_modified_caps"] is False
    assert reports["final_report_v66.json"]["verdict"] == "PARTIAL"


def test_v66_exact_packet_validates_no_live_action() -> None:
    reports = generate_all_v66_reports_for_tests(approval_input=v70_packet())
    validator = reports["v66_approval_packet_validator_report.json"]
    assert validator["approval_packet_validator_status"] == "PASS_LIVE_CANARY_APPROVAL_PACKET_VALID"
    assert validator["approval_validated"] is True
    assert validator["live_order_placed"] is False
    assert reports["final_report_v66.json"]["verdict"] == "PASS"
    assert_staged_safe(validator)


def test_v66_fuzzy_packet_fails_closed() -> None:
    validator = generate_all_v66_reports_for_tests(approval_input=v70_packet("I approve a live canary"))["v66_approval_packet_validator_report.json"]
    assert validator["approval_packet_validator_status"] == "FAIL_CLOSED_INVALID_APPROVAL"


def test_v66_safety_and_locks() -> None:
    for name, report in generate_all_v66_reports_for_tests().items():
        if name == "final_report_v66.json":
            continue
        assert_staged_safe(report)
