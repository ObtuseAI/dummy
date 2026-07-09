from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_bea_macro_adapter_blocks_missing_key() -> None:
    report = assert_v20_report("bea_macro_adapter_report_v1.json", "adapter_status")
    assert report["adapter_status"] == "BLOCKED_KEY_MISSING"

