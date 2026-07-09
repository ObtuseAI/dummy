from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_readonly_only_source_activation_v20_report_passes() -> None:
    report = assert_security_report("generate_readonly_only_source_activation_report_v20")
    assert report["read_only_only"] is True
    assert report["write_endpoints_called"] == []

