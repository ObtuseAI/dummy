from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_weather_edge_feature_map_has_freshness_and_disagreement() -> None:
    report = assert_v20_report("weather_edge_feature_map_report_v1.json", "features")
    features = {feature["feature"] for feature in report["features"]}
    assert {"forecast freshness", "model disagreement"} <= features
