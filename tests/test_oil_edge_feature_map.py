from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_oil_edge_feature_map_has_required_energy_features() -> None:
    report = assert_v20_report("oil_edge_feature_map_report_v1.json", "features")
    features = {feature["feature"] for feature in report["features"]}
    assert {"curve structure", "inventory surprise context", "weather disruption risk", "contradiction score"} <= features

