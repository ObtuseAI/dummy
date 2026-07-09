from predator_mesh.v30.adapters import (
    AdapterNormalizationPipelineV1,
    AdapterRequestV1,
    FixtureMode,
    WeatherPublicObservationAdapterV1,
)
from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_normalization_pipeline_v1_classifies_fixture_sample_cached_and_invalid_evidence() -> None:
    pipeline = AdapterNormalizationPipelineV1()
    adapter = WeatherPublicObservationAdapterV1()
    packet = pipeline.normalize(
        adapter.fetch(
            AdapterRequestV1(
                adapter_id=adapter.adapter_id,
                market_class="WEATHER_THRESHOLD",
                metric="temperature_f",
                target={"station": "KCMO"},
                fixture_id="weather_kc_temperature_fixture",
                mode=FixtureMode.REPLAY_FIXTURE,
            )
        )
    )

    assert packet.evidence_class == "FIXTURE_REPLAY_ONLY"
    assert packet.source_mode == "REPLAY_FIXTURE"
    assert packet.live_observation_eligible is False
    assert packet.live_score_eligible is False
    assert packet.provenance


def test_adapter_normalization_pipeline_v1_report_contract() -> None:
    report = assert_v30_report_named("adapter_normalization_pipeline_v1_report.json", "adapter_normalization_status")
    assert report["adapter_normalization_status"] == "PASS"
    assert report["normalized_evidence_packet_count"] >= 4
    assert report["live_score_from_normalization"] is False
