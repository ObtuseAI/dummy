from predator_mesh.v30.adapters import AdapterRequestV1, FixtureMode, WeatherPublicObservationAdapterV1
from tests.v30_test_helpers import assert_v30_report_named


def test_weather_public_observation_adapter_v1_normalizes_fixture_and_settlement_compatibility() -> None:
    adapter = WeatherPublicObservationAdapterV1()
    request = AdapterRequestV1(
        adapter_id=adapter.adapter_id,
        market_class="WEATHER_THRESHOLD",
        metric="temperature_f",
        target={"station": "KCMO", "threshold": 80},
        fixture_id="weather_kc_temperature_fixture",
        mode=FixtureMode.REPLAY_FIXTURE,
    )
    response = adapter.fetch(request)

    assert response.metric == "temperature_f"
    assert response.value == 82.4
    assert response.blocker is None
    assert response.freshness_status == "FIXTURE_NOT_LIVE"
    assert response.to_evidence_packet().settlement_compatible is True
    assert response.to_evidence_packet().live_score_eligible is False


def test_weather_public_observation_adapter_v1_returns_metric_incompatible_blocker() -> None:
    adapter = WeatherPublicObservationAdapterV1()
    response = adapter.fetch(
        AdapterRequestV1(
            adapter_id=adapter.adapter_id,
            market_class="WEATHER_THRESHOLD",
            metric="wind_speed_mph",
            target={"station": "KCMO"},
            fixture_id="weather_kc_temperature_fixture",
            mode=FixtureMode.REPLAY_FIXTURE,
        )
    )

    assert response.blocker == "METRIC_INCOMPATIBLE"
    assert response.to_evidence_packet().evidence_class == "INVALID"


def test_weather_public_observation_adapter_v1_report_contract() -> None:
    report = assert_v30_report_named("weather_public_observation_adapter_v1_report.json", "weather_adapter_status")
    assert report["weather_adapter_status"] == "PASS"
    assert report["no_live_score_from_fixture"] is True
