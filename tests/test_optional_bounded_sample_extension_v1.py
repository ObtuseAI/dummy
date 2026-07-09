from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report, v42_enabled_reports


def test_optional_bounded_sample_extension_v1_respects_budget() -> None:
    report = assert_current_test_report(__file__)
    assert report["real_probe_run_allowed"] is False
    assert report["max_optional_cycles"] == 2
    assert report["max_total_requests"] == 12
    enabled = v42_enabled_reports()["optional_bounded_sample_extension_v1_report.json"]
    assert enabled["optional_sample_extension_status"] == "PASS_OPTIONAL_SAMPLE_EXTENSION"
    assert enabled["v42_new_real_probe_count"] == 6
    assert enabled["sports_excluded"] is True
