from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_weather_no_trade_gate_v2_blocks_model_data_plan_gap() -> None:
    report = assert_v20_report("weather_no_trade_gate_v2_report.json", "no_trade_reasons")
    assert report["no_trade"] is True
