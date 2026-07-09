from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v47_test_helpers import StableSampleReadOnlyTransport, v47_reports


def test_v47_default_blocks_without_exact_gate() -> None:
    reports = v47_reports()
    report = reports["v47_stable_sample_threshold_controller_report.json"]
    assert report["stable_sample_threshold_controller_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v46_cumulative_real_scored_count"] >= 81
    assert report["v47_new_real_probe_count"] == 0
    assert report["v47_new_real_scored_count"] == 0
    assert report["cumulative_real_scored_count"] == report["v46_cumulative_real_scored_count"]
    assert report["score_gap_to_100"] == 19
    assert report["stable_sample_candidate_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["gate_visible_in_runtime_process"] is False


def test_v47_enabled_reaches_stable_sample_review_without_trading_readiness() -> None:
    transport = StableSampleReadOnlyTransport()
    reports = v47_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=transport)
    report = reports["v47_stable_sample_threshold_controller_report.json"]
    assert report["stable_sample_threshold_controller_status"] == "PASS_READONLY_STABLE_SAMPLE_THRESHOLD_CLOSURE"
    assert report["max_observer_lanes"] == 4
    assert report["max_cycles_per_lane"] == 3
    assert report["max_total_requests"] == 36
    assert 19 <= report["v47_new_real_scored_count"] <= 30
    assert 100 <= report["cumulative_real_scored_count"] <= 111
    assert report["score_gap_to_100"] == 0
    assert report["stable_sample_candidate_status"] == "STABLE_SAMPLE_CANDIDATE_REVIEW_READONLY"
    assert report["stable_sample_candidate_unlocked"] is True
    assert report["readiness_exposed_stage"] == "READONLY_STABLE_SAMPLE_REVIEW"
    assert report["live_trading_readiness_claim"] is False
    assert report["stable_sample_candidate_live_trading_readiness_claim"] is False
    assert report["execution_lock_v6_status"] == "PASS"
    assert len(transport.calls) <= 36
