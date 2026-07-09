from tests.v29_test_helpers import assert_current_test_report


def test_no_public_probe_readiness_to_execution_bridge_v29_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["public_probe_readiness_to_execution_bridge_present"] is False
    assert report["integration_mode_status"] == "DISABLED_BY_DEFAULT"
    assert report["live_execution_enabled"] is False
    assert report["private_endpoints_used"] is False
