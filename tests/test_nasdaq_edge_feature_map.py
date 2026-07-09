from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nasdaq_edge_feature_map_has_required_direction_features() -> None:
    report = assert_v20_report("nasdaq_edge_feature_map_report_v1.json", "features")
    features = {feature["feature"] for feature in report["features"]}
    assert {"futures trend", "mega-cap breadth", "vol regime", "contradiction score"} <= features

