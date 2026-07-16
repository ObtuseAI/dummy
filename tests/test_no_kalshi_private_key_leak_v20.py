from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_kalshi_private_key_leak_v20_report_passes() -> None:
    report = assert_security_report("generate_no_kalshi_private_key_leak_report_v20")
    assert report["private_key_material_found"] is False
