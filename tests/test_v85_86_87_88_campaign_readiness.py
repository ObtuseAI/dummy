from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v85_reports import generate_all_v85_reports_for_tests
from archive.report_scripts.generate_v86_reports import generate_all_v86_reports_for_tests
from archive.report_scripts.generate_v87_reports import generate_all_v87_reports_for_tests
from archive.report_scripts.generate_v88_reports import generate_all_v88_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


class FakeFirewall:
    def submit(self, order):
        return {"order_attempt_id": "x", "accepted": True, "real_broker_contacted": False}


def campaign_approval() -> dict:
    return {"exact_phrase": sgc.MICRO_CAMPAIGN_PHRASE, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "prepare micro-campaign gate", "scope": sgc.MICRO_CAMPAIGN_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def test_v85_blocker_audit_passes() -> None:
    reports = generate_all_v85_reports_for_tests()
    c = reports["v85_blocker_closure_controller_report.json"]
    assert_staged_safe(c)
    assert c["v84_baseline_status"] == "PASS_V84_BASELINE_READBACK"
    assert c["blocker_closure_controller_status"] == "PASS_CAMPAIGN_BLOCKERS_CLASSIFIED_NO_SUBMIT"
    assert c["no_auto_submit_proof_status"] == "PASS_NO_AUTO_SUBMIT"
    assert c["live_orders"] == 0
    assert c["current_next_action"] == "AWAIT_CAMPAIGN_AND_PER_ORDER_APPROVALS"
    assert reports["final_report_v85.json"]["verdict"] == "PASS"


def test_v86_partial_default_pass_with_campaign_approval() -> None:
    default = generate_all_v86_reports_for_tests()["v86_approval_registry_controller_report.json"]
    assert default["approval_registry_controller_status"] == "PARTIAL_CAMPAIGN_APPROVAL_ABSENT"
    assert_staged_safe(default)
    approved = generate_all_v86_reports_for_tests(campaign_approval=campaign_approval())["v86_approval_registry_controller_report.json"]
    assert approved["approval_registry_controller_status"] == "PASS_CAMPAIGN_APPROVED_PER_ORDER_REGISTRY_LOCKED"
    assert approved["per_order_registry_locked_until_each_file_exists"] is True
    assert approved["raw_phrase_serialized"] is False


def test_v87_partial_default_ready_with_config_adapter() -> None:
    default = generate_all_v87_reports_for_tests()["v87_readiness_controller_report.json"]
    assert default["readiness_controller_status"] == "PARTIAL_LIVE_CONFIG_OR_ADAPTER_ABSENT"
    assert default["broker_contacted"] is False
    ready = generate_all_v87_reports_for_tests(live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())["v87_readiness_controller_report.json"]
    assert ready["readiness_controller_status"] == "PASS_LIVE_CONFIG_CAPS_FIREWALL_READY_NO_CONTACT"
    assert ready["broker_contacted"] is False
    assert_staged_safe(ready)


def test_v88_candidate_queue_submit_disabled() -> None:
    reports = generate_all_v88_reports_for_tests()
    c = reports["v88_candidate_queue_controller_report.json"]
    assert_staged_safe(c)
    assert c["candidate_queue_controller_status"] == "PASS_CANDIDATE_QUEUE_READY_SUBMIT_DISABLED"
    assert c["submit_enabled_default"] is False
    assert c["abstention_governor_status"] == "PASS_ABSTENTION_GOVERNOR_ACTIVE"
    assert c["broker_payload_present"] is False
    assert len(c["abstention_rules"]) == 10
    assert reports["final_report_v88.json"]["verdict"] == "PASS"


def test_v85_88_safety_and_locks() -> None:
    for gen in (generate_all_v85_reports_for_tests, generate_all_v86_reports_for_tests, generate_all_v87_reports_for_tests, generate_all_v88_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
