import pytest

from predator_mesh.v30.adapters import AdapterFixtureLoaderV1, FixtureMode
from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_fixture_contract_implementation_v1_loads_valid_and_rejects_malformed_fixture() -> None:
    loader = AdapterFixtureLoaderV1()
    fixture = loader.load("weather_kc_temperature_fixture")

    assert fixture.fixture_id == "weather_kc_temperature_fixture"
    assert fixture.mode == FixtureMode.REPLAY_FIXTURE
    assert fixture.source_label
    assert loader.mode_guard(fixture)["live_score_allowed"] is False

    with pytest.raises(ValueError, match="MALFORMED_FIXTURE"):
        loader.validate({"fixture_id": "bad"})


def test_adapter_fixture_contract_implementation_v1_report_contract() -> None:
    report = assert_v30_report_named(
        "adapter_fixture_contract_implementation_v1_report.json",
        "fixture_contract_status",
        "fixture_contract_count",
    )
    assert report["fixture_contract_status"] == "PASS"
    assert report["fixture_contract_count"] >= 4
    assert report["fixture_responses_claimed_live"] is False
