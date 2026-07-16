from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_direction_terrain_stack_has_no_perp_execution() -> None:
    report = assert_v20_report("crypto_direction_terrain_stack_report_v1.json", "required_source_needs")
    assert report["live_execution_enabled"] is False
    assert "CCXT public adapter" in report["required_source_needs"]
