from __future__ import annotations

from predator_mesh.v31.probes import (
    DueForecastLiveObservationClosureV4,
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_v31_report_named


def _enabled_normalized_packets():
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    return ProbeEvidenceNormalizationPipelineV2().normalize_live_packets(LivePublicEvidenceCaptureV1().capture(run))


def test_due_forecast_closure_observes_only_due_matching_live_public_evidence() -> None:
    closure = DueForecastLiveObservationClosureV4().close(_enabled_normalized_packets())

    assert closure.due_forecast_count == 4
    assert closure.observed_forecast_count == 3
    assert closure.live_unresolved_count == 1
    assert "SETTLEMENT_AMBIGUOUS" in closure.blockers
    assert all(decision.score_seed_eligible is True for decision in closure.decisions if decision.status == "OBSERVED_LIVE_PUBLIC")
    assert closure.outcome_fabricated is False
    assert closure.execution_bridge_present is False


def test_due_forecast_closure_disabled_state_has_exact_blocker() -> None:
    closure = DueForecastLiveObservationClosureV4().close([])

    assert closure.due_forecast_count == 4
    assert closure.observed_forecast_count == 0
    assert closure.live_unresolved_count == 4
    assert "NO_MATCHING_LIVE_PUBLIC_EVIDENCE" in closure.blockers
    assert closure.unresolved_forecast_scored is False


def test_due_forecast_live_observation_closure_report_contract() -> None:
    report = assert_v31_report_named(
        "due_forecast_live_observation_closure_v4_report.json",
        "due_forecast_observation_closure_status",
    )
    assert report["due_forecast_observation_closure_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["observed_forecast_count"] == 0
    assert report["live_unresolved_count"] >= 1
