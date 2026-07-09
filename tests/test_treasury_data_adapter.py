from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_treasury_data_adapter_is_public_readonly() -> None:
    report = assert_v20_report("treasury_data_adapter_report_v1.json", "read_only_only")
    assert report["private_endpoints_used"] is False

