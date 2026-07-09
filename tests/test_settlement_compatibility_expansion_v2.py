from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_settlement_compatibility_expansion_v2_joins_by_market_class() -> None:
    report = assert_current_test_report(__file__)
    assert report["scores_created_here"] is False
    assert report["weather_joins_weather_only"] is True
    enabled = v41_enabled_reports()["settlement_compatibility_expansion_v2_report.json"]
    assert enabled["v41_new_settlement_compatible_count"] >= 6
    assert enabled["ambiguous_join_blocker"] == "SETTLEMENT_AMBIGUOUS"
