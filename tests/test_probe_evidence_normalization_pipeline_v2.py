from __future__ import annotations

from predator_mesh.v30.adapters import build_default_v30_context
from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_v31_report_named


def test_probe_normalization_rejects_v30_fixtures_as_live_public_evidence() -> None:
    fixture_packets = build_default_v30_context()["packets"]
    normalized = ProbeEvidenceNormalizationPipelineV2().normalize_fixture_packets(fixture_packets)

    assert len(normalized) == 4
    assert all(item.live_observation_eligible is False for item in normalized)
    assert all(item.live_score_eligible is False for item in normalized)
    assert {item.mode for item in normalized} >= {
        "REPLAY_FIXTURE_RESPONSE",
        "PUBLIC_SAMPLE_RESPONSE",
        "CACHED_PUBLIC_PROBE_RESULT",
    }


def test_probe_normalization_allows_live_public_probe_results_to_feed_observation_not_score() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    packets = LivePublicEvidenceCaptureV1().capture(run)
    normalized = ProbeEvidenceNormalizationPipelineV2().normalize_live_packets(packets)

    assert len(normalized) == 3
    assert all(item.mode == "LIVE_PUBLIC_PROBE_RESULT" for item in normalized)
    assert all(item.live_observation_eligible is True for item in normalized)
    assert all(item.live_score_eligible is False for item in normalized)


def test_probe_evidence_normalization_report_contract() -> None:
    report = assert_v31_report_named("probe_evidence_normalization_pipeline_v2_report.json", "probe_evidence_normalization_status")
    assert report["probe_evidence_normalization_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["normalized_live_public_evidence_count"] == 0
    assert report["fixture_evidence_live_observation_allowed"] is False
