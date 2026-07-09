from tests.v26_test_helpers import assert_current_test_report


def test_keyless_adapter_probe_orchestrator_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["background_daemon"] is False
    assert report["unit_tests_use_fixtures"] is True
    assert report["real_calls_only_in_report_generator_or_integration_mode"] is True
    assert report["max_probes_per_run"] <= 12
    assert report["unbounded_downloads"] is False
