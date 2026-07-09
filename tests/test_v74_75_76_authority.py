from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v74_reports import generate_all_v74_reports_for_tests
from scripts.generate_v75_reports import generate_all_v75_reports_for_tests
from scripts.generate_v76_reports import generate_all_v76_reports_for_tests
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


def test_v74_blocker_closure_audit_passes() -> None:
    reports = generate_all_v74_reports_for_tests()
    controller = reports["v74_blocker_closure_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v73_baseline_status"] == "PASS_V73_BASELINE_READBACK"
    assert controller["blocker_closure_controller_status"] == "PASS_BLOCKERS_CLASSIFIED_NO_SUBMIT"
    assert "LIVE_CANARY_APPROVAL_ABSENT" in controller["classified_blockers"]
    assert controller["no_submit_proof_status"] == "PASS_NO_SUBMIT"
    assert reports["final_report_v74.json"]["verdict"] == "PASS"


def test_v75_partial_without_approval_and_config() -> None:
    reports = generate_all_v75_reports_for_tests()
    controller = reports["v75_config_tieout_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["config_tieout_controller_status"] == "PARTIAL_LIVE_CANARY_APPROVAL_OR_CONFIG_ABSENT"
    assert controller["dummy_enabled_live_submit"] is False
    assert controller["dummy_modified_caps"] is False
    assert reports["final_report_v75.json"]["verdict"] == "PARTIAL"


def test_v75_tied_out_with_full_config_no_submit() -> None:
    controller = generate_all_v75_reports_for_tests(approval_input=v70_packet(), live_submit_operator_enabled=True, caps_config_present=True)["v75_config_tieout_controller_report.json"]
    assert controller["config_tieout_controller_status"] == "PASS_LIVE_CONFIG_CAPS_APPROVAL_TIED_OUT_NO_SUBMIT"
    assert controller["approval_validated"] is True
    assert_staged_safe(controller)


def test_v76_blocked_by_default_ready_with_override() -> None:
    reports = generate_all_v76_reports_for_tests()
    controller = reports["v76_authorization_packet_controller_report.json"]
    assert controller["authorization_packet_controller_status"] == "PARTIAL_SINGLE_CANARY_AUTH_PACKET_BLOCKED"
    assert reports["final_report_v76.json"]["verdict"] == "PARTIAL"
    ready = generate_all_v76_reports_for_tests(v75_ready_override=True)["v76_authorization_packet_controller_report.json"]
    assert ready["authorization_packet_controller_status"] == "PASS_SINGLE_CANARY_AUTH_PACKET_READY_NO_SUBMIT"
    assert ready["execution_path_created"] is False
    assert_staged_safe(ready)


def test_v74_75_76_safety_and_locks() -> None:
    for gen in (generate_all_v74_reports_for_tests, generate_all_v75_reports_for_tests, generate_all_v76_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
