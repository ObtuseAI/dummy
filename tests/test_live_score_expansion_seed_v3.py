from __future__ import annotations

from predator_mesh.v32.recovery import (
    DueForecastClosureExpansionV5,
    LiveCalibrationExpansionV3,
    LivePublicEvidenceExpansionV2,
    LiveScoreExpansionSeedV3,
    SettlementCompatibleEvidenceExpansionV2,
    build_default_v32_state,
)
from tests.v32_test_helpers import assert_v32_report_named


def test_live_score_expansion_scores_only_observed_live_public_outcomes() -> None:
    state = build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    settlement = SettlementCompatibleEvidenceExpansionV2().expand(LivePublicEvidenceExpansionV2().expand(state))
    closure = DueForecastClosureExpansionV5().close(settlement)
    score = LiveScoreExpansionSeedV3().seed(closure)

    assert score.live_score_expansion_status == "PASS"
    assert score.live_scored_count == 3
    assert score.disabled_probe_scored_live is False
    assert score.public_probe_failure_scored_live is False
    assert score.ambiguous_settlement_scored is False
    assert score.execution_bridge_present is False


def test_live_calibration_expansion_uses_only_score_expansion() -> None:
    state = build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    settlement = SettlementCompatibleEvidenceExpansionV2().expand(LivePublicEvidenceExpansionV2().expand(state))
    score = LiveScoreExpansionSeedV3().seed(DueForecastClosureExpansionV5().close(settlement))
    calibration = LiveCalibrationExpansionV3().expand(score)

    assert calibration.live_calibration_expansion_status == "PASS_LOW_SAMPLE_WARNING"
    assert calibration.live_calibration_sample_count == 3
    assert calibration.execution_bridge_present is False


def test_live_score_expansion_seed_report_contract() -> None:
    report = assert_v32_report_named("live_score_expansion_seed_v3_report.json", "live_score_expansion_status")
    assert report["live_score_expansion_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_scored_count"] == 0
