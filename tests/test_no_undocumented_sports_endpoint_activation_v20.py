from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_undocumented_sports_endpoint_activation_v20_report_passes() -> None:
    report = assert_security_report("generate_no_undocumented_sports_endpoint_activation_report_v20")
    assert report["undocumented_sports_endpoints_activated"] == []
