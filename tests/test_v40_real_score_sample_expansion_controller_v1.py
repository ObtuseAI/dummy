from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v40.reports import V40ReportFactory
from tests.v40_test_helpers import ExpandedReadOnlyTransport, assert_current_test_report


def test_v40_real_score_sample_expansion_controller_v1_default_blocks_without_gate() -> None:
    report = assert_current_test_report(__file__)
    assert report["sample_expansion_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["baseline_real_scored_count"] >= 3
    assert report["v40_new_real_scored_count"] == 0
    assert report["cumulative_real_scored_count"] >= report["baseline_real_scored_count"]
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v40_enabled_expands_real_score_sample_with_injected_transport() -> None:
    reports = V40ReportFactory(
        env=EXACT_GATE_ENV,
        enable_real_probe=True,
        real_transport=ExpandedReadOnlyTransport(),
    ).build()
    report = reports["v40_real_score_sample_expansion_controller_v1_report.json"]
    assert report["sample_expansion_status"] == "PASS_REAL_LIVE_SCORE_SAMPLE_EXPANSION"
    assert report["v40_new_real_probe_count"] > 0
    assert report["v40_new_evidence_count"] > 0
    assert report["v40_new_real_scored_count"] > 0
    assert report["cumulative_real_scored_count"] > report["baseline_real_scored_count"]
    assert report["live_trading_readiness_claim"] is False
