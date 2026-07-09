from tests.v27_test_helpers import assert_current_test_report


def test_integration_mode_public_probe_controller_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["integration_probes_enabled"] is False
    assert report["unit_tests_use_fixtures"] is True
    assert report["background_daemon"] is False
    assert report["all_probes_read_only"] is True
    assert report["execution_bridge_present"] is False
