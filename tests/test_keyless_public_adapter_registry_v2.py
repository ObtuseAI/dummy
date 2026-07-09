from tests.v26_test_helpers import assert_current_test_report


def test_keyless_public_adapter_registry_v2_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["keyless_adapter_active_count"] >= 8
    assert "WEATHER_THRESHOLD" in report["market_classes_supported"]
    assert "CRYPTO_PRICE_RANGE" in report["market_classes_supported"]
    assert "KALSHI_MARKET_MAPPED" in report["market_classes_supported"]
    assert report["premium_or_keyed_sources_are_global_blockers"] is False
