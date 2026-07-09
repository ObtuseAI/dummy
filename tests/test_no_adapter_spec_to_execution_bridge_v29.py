from tests.v29_test_helpers import assert_current_test_report


def test_no_adapter_spec_to_execution_bridge_v29_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["adapter_spec_to_execution_bridge_present"] is False
    assert report["live_execution_enabled"] is False
    assert report["model_can_submit_orders"] is False
    assert report["order_endpoints_used"] is False
