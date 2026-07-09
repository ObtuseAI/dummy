from __future__ import annotations

from predator_mesh.v33.run import LiveScoreObservationRunV4, build_default_v33_state
from tests.v33_test_helpers import assert_v33_report_named


def test_live_score_observation_run_default_disabled_scores_nothing() -> None:
    state = build_default_v33_state(enable_network=False)
    score = state["live_score_observation_run"]

    assert score.live_score_observation_run_status == "PASS_DISABLED_BY_DEFAULT"
    assert score.live_scored_count == 0
    assert score.disabled_probe_scored_live is False
    assert score.public_probe_failure_scored_live is False


def test_live_score_observation_run_enabled_scores_only_observed_live_public() -> None:
    state = build_default_v33_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    score = LiveScoreObservationRunV4().score(state["due_forecast_observation_run"])

    assert score.live_score_observation_run_status == "PASS"
    assert score.live_scored_count == 3
    assert all(record["score_source"] == "OBSERVED_LIVE_PUBLIC" for record in score.score_records)
    assert score.ambiguous_settlement_scored is False


def test_live_score_observation_run_report_contract() -> None:
    report = assert_v33_report_named("live_score_observation_run_v4_report.json", "live_score_observation_run_status")

    assert report["live_score_observation_run_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_scored_count"] == 0
