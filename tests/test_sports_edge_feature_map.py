from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sports_edge_feature_map_has_weather_and_settlement_features() -> None:
    report = assert_v20_report("sports_edge_feature_map_report_v1.json", "features")
    features = {feature["feature"] for feature in report["features"]}
    assert {"weather impact", "settlement mapping quality"} <= features

