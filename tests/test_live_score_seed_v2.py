from __future__ import annotations

from predator_mesh.v31.probes import (
    DueForecastLiveObservationClosureV4,
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LiveCalibrationSeedV2,
    LivePublicEvidenceCaptureV1,
    LiveScoreSeedV2,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_v31_report_named


def _enabled_closure():
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    packets = ProbeEvidenceNormalizationPipelineV2().normalize_live_packets(LivePublicEvidenceCaptureV1().capture(run))
    return DueForecastLiveObservationClosureV4().close(packets)


def test_live_score_seed_scores_only_observed_live_public_outcomes() -> None:
    seed = LiveScoreSeedV2().seed(_enabled_closure())

    assert seed.live_scored_count == 3
    assert seed.fixture_scored_live is False
    assert seed.adapter_dry_run_scored_live is False
    assert seed.public_sample_scored_live is False
    assert seed.stale_cached_evidence_scored_live is False
    assert seed.ambiguous_settlement_scored is False
    assert seed.source_unavailable_forecast_scored is False
    assert seed.execution_bridge_present is False


def test_live_calibration_seed_uses_only_live_score_seed_samples() -> None:
    score_seed = LiveScoreSeedV2().seed(_enabled_closure())
    calibration = LiveCalibrationSeedV2().seed(score_seed)

    assert calibration.live_calibration_seed_status == "PASS_LOW_SAMPLE_WARNING"
    assert calibration.live_calibration_sample_count == 3
    assert calibration.low_sample_warning is True
    assert calibration.execution_bridge_present is False


def test_live_score_seed_report_contract() -> None:
    report = assert_v31_report_named("live_score_seed_v2_report.json", "live_score_seed_status")
    assert report["live_score_seed_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_scored_count"] == 0
    assert report["no_valid_live_public_outcomes_scored"] is True
