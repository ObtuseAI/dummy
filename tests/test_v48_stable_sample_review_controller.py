from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v48_test_helpers import StableSampleReviewReadOnlyTransport, v48_reports


def test_v48_default_blocks_without_exact_gate_after_v47_readback() -> None:
    reports = v48_reports()
    report = reports["v48_stable_sample_review_controller_report.json"]
    assert report["stable_sample_review_verdict"] == "PARTIAL_REVIEW_BLOCKED"
    assert report["v47_baseline_status"] == "PASS_V47_BASELINE_READBACK"
    assert report["v47_cumulative_real_scored_count"] >= 108
    assert report["v48_new_real_scored_count"] == 0
    assert report["cumulative_real_scored_count"] == report["v47_cumulative_real_scored_count"]
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v48_enabled_passes_stable_sample_review_readonly() -> None:
    transport = StableSampleReviewReadOnlyTransport()
    reports = v48_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=transport)
    report = reports["v48_stable_sample_review_controller_report.json"]
    assert report["stable_sample_review_verdict"] == "PASS_STABLE_SAMPLE_REVIEW_READONLY"
    assert 0 <= report["v48_new_real_scored_count"] <= 24
    assert report["cumulative_real_scored_count"] >= 108
    assert report["robustness_review_status"] == "PASS"
    assert report["locked_rehearsal_gate_design_status"] == "PASS_LOCKED_DESIGN_ONLY"
    assert report["readiness_governor_v8_status"] == "PASS"
    assert report["execution_lock_v7_status"] == "PASS"
    assert report["live_trading_readiness_claim"] is False
    assert len(transport.calls) <= 24
