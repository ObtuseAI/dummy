from __future__ import annotations

from scripts.generate_v69_reports import generate_all_v69_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v69_final_tieout_ready_no_submit() -> None:
    reports = generate_all_v69_reports_for_tests()
    controller = reports["v69_final_tieout_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v68_baseline_status"] == "PASS_V68_BASELINE_READBACK"
    assert controller["final_tieout_controller_status"] == "PASS_FINAL_TIEOUT_READY_NO_SUBMIT"
    assert controller["no_submit_no_cancel_proof_status"] == "PASS_NO_SUBMIT_NO_CANCEL"
    assert controller["livebrokerfirewall_only_proof_status"] == "PASS_LIVEBROKERFIREWALL_ONLY"
    assert controller["no_direct_broker_bypass_proof_status"] == "PASS_NO_DIRECT_BROKER_BYPASS"
    assert controller["live_submit_status_proof_status"] == "PASS_LIVE_SUBMIT_OPERATOR_CONTROLLED_DISABLED"
    assert controller["live_order_fired"] is False
    assert controller["broker_payload_sent"] is False
    assert reports["final_report_v69.json"]["verdict"] == "PASS"


def test_v69_safety_and_locks() -> None:
    for name, report in generate_all_v69_reports_for_tests().items():
        if name == "final_report_v69.json":
            continue
        assert_staged_safe(report)
