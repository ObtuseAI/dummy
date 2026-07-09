from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_source_api_key_leak_v20_report_passes() -> None:
    report = assert_security_report("generate_no_source_api_key_leak_report_v20")
    assert report["source_api_key_values_found"] is False

