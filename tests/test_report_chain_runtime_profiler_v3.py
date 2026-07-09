from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_report_chain_runtime_profiler_v3_is_finite_through_v20() -> None:
    report = assert_v20_report("report_chain_runtime_profiler_v3_report.json", "generators")
    assert report["report_chain_finite"] is True
    assert "generate_v20_reports.py" in report["generators"]

