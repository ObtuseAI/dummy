from tests.v25_test_helpers import assert_current_test_report


def test_market_class_ontology_covers_canonical_scope_without_example_centering() -> None:
    report = assert_current_test_report(__file__)
    assert report["market_class_ontology_status"] == "PASS"
    families = set(report["market_class_families"])
    assert "WEATHER_THRESHOLD" in families
    assert "CRYPTO_PRICE_THRESHOLD" in families
    assert "SPORTS_GAME_RESULT" in families
    assert "COMMODITY_REFERENCE_EVENT" in families
    assert "FINANCE_MARKET_DIRECTION" in families
    assert "MACRO_POLICY_EVENT" in families
    assert "KALSHI_MARKET_MAPPED" in families
    assert report["example_market_canonical_center"] is False
