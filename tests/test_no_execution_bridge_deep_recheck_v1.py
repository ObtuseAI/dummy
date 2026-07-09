from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_no_execution_bridge_deep_recheck_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_execution_bridge_deep_recheck_v1_status"] == "PASS"
    assert report["all_pass"] is True
    assert report["execution_bridge_present"] is False
    assert set(report["subchecks"]) == {
        "adapter_no_execution_bridge_check",
        "probe_no_execution_bridge_check",
        "evidence_no_execution_bridge_check",
        "scoring_no_execution_bridge_check",
        "calibration_no_execution_bridge_check",
        "source_truth_no_execution_bridge_check",
        "dashboard_no_execution_bridge_check",
    }


def test_each_subcheck_reports_no_bridge() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    for name in [
        "adapter_no_execution_bridge_check_report.json",
        "probe_no_execution_bridge_check_report.json",
        "evidence_no_execution_bridge_check_report.json",
        "scoring_no_execution_bridge_check_report.json",
        "calibration_no_execution_bridge_check_report.json",
        "source_truth_no_execution_bridge_check_report.json",
        "dashboard_no_execution_bridge_check_report.json",
    ]:
        report = assert_v35_report_named(name)
        assert report["no_order_cancel_submit"] is True
        assert report["no_execution_clients_imported"] is True
        assert report["no_live_submit_or_caps_touch"] is True
