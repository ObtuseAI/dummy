from predator_mesh.v30.adapters import (
    AdapterRequestV1,
    AdapterToSettlementCompatibilityV1,
    FixtureMode,
    WeatherPublicObservationAdapterV1,
)
from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_to_settlement_compatibility_v1_allows_matching_weather_rule_and_blocks_cross_domain() -> None:
    adapter = WeatherPublicObservationAdapterV1()
    packet = adapter.fetch(
        AdapterRequestV1(
            adapter_id=adapter.adapter_id,
            market_class="WEATHER_THRESHOLD",
            metric="temperature_f",
            target={"station": "KCMO"},
            fixture_id="weather_kc_temperature_fixture",
            mode=FixtureMode.REPLAY_FIXTURE,
        )
    ).to_evidence_packet()
    compatibility = AdapterToSettlementCompatibilityV1()

    ok = compatibility.join(packet, {"market_class": "WEATHER_THRESHOLD", "metric": "temperature_f"})
    blocked = compatibility.join(packet, {"market_class": "CRYPTO_PRICE_THRESHOLD", "metric": "btc_usd"})

    assert ok.decision == "COMPATIBLE_PIPELINE_ONLY"
    assert ok.live_score_allowed is False
    assert blocked.decision == "INCOMPATIBLE_MARKET_CLASS"
    assert blocked.live_score_allowed is False


def test_adapter_to_settlement_compatibility_v1_report_contract() -> None:
    report = assert_v30_report_named(
        "adapter_to_settlement_compatibility_v1_report.json",
        "adapter_to_settlement_compatibility_status",
    )
    assert report["adapter_to_settlement_compatibility_status"] == "PASS"
    assert report["settlement_compatible_packet_count"] >= 3
    assert report["fixture_join_live_score_allowed"] is False
