from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_eia_energy_adapter_blocks_missing_key_without_secret_value() -> None:
    report = assert_v20_report("eia_energy_adapter_report_v1.json", "adapter_status")
    assert report["adapter_status"] == "BLOCKED_KEY_MISSING"
    assert report["secret_values_exposed"] is False
