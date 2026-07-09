from predator_mesh.v30.adapters import (
    AdapterRequestV1,
    AdapterRuntimeGuardV1,
    FixtureMode,
    WeatherPublicObservationAdapterV1,
)
from tests.v30_test_helpers import assert_v30_report_named


def test_in_house_adapter_base_interface_v1_returns_standard_response_without_execution_methods() -> None:
    request = AdapterRequestV1(
        adapter_id="weather_public_observation_v1",
        market_class="WEATHER_THRESHOLD",
        metric="temperature_f",
        target={"station": "KCMO", "threshold": 80},
        fixture_id="weather_kc_temperature_fixture",
        mode=FixtureMode.REPLAY_FIXTURE,
    )
    response = WeatherPublicObservationAdapterV1().fetch(request)
    packet = response.to_evidence_packet()

    assert response.source_name == "weather_public_observation_v1"
    assert response.source_mode == FixtureMode.REPLAY_FIXTURE.value
    assert response.evidence_role == "PUBLIC_READONLY_OBSERVATION"
    assert response.settlement_role == "WEATHER_THRESHOLD_SETTLEMENT"
    assert response.value == 82.4
    assert packet.evidence_class == "FIXTURE_REPLAY_ONLY"
    assert packet.live_observation_eligible is False
    assert packet.live_score_eligible is False
    assert packet.execution_bridge_present is False
    assert AdapterRuntimeGuardV1().assert_safe()["execution_methods_present"] is False


def test_in_house_adapter_base_interface_v1_report_contract() -> None:
    report = assert_v30_report_named("in_house_adapter_base_interface_v1_report.json", "base_interface_status")
    assert report["base_interface_status"] == "PASS"
    assert report["execution_methods_present"] is False
    assert report["order_cancel_account_balance_methods_present"] is False
