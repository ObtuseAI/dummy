from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_edge_feature_map_has_divergence_and_volatility() -> None:
    report = assert_v20_report("crypto_edge_feature_map_report_v1.json", "features")
    features = {feature["feature"] for feature in report["features"]}
    assert {"cross-exchange divergence", "volatility regime"} <= features

