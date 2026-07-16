from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_commercial_source_without_approval_v20_report_passes() -> None:
    report = assert_security_report("generate_no_commercial_source_without_approval_report_v20")
    assert report["commercial_sources_activated_without_approval"] == []
