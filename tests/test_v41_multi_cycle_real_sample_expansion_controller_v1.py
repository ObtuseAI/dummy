from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v41.reports import V41ReportFactory
from tests.v41_test_helpers import MultiCycleReadOnlyTransport, assert_current_test_report


def test_v41_multi_cycle_controller_default_blocks_without_gate() -> None:
    report = assert_current_test_report(__file__)
    assert report["multi_cycle_expansion_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v40_cumulative_real_scored_count"] >= 6
    assert report["v41_new_real_scored_count"] == 0
    assert report["cumulative_real_scored_count"] >= report["v40_cumulative_real_scored_count"]
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v41_enabled_runs_bounded_multi_cycle_expansion_with_injected_transport() -> None:
    reports = V41ReportFactory(
        env=EXACT_GATE_ENV,
        enable_real_probe=True,
        real_transport=MultiCycleReadOnlyTransport(),
    ).build()
    report = reports["v41_multi_cycle_real_sample_expansion_controller_v1_report.json"]
    assert report["multi_cycle_expansion_status"] == "PASS_REAL_PUBLIC_PROBE_EXPANSION"
    assert 2 <= report["v41_probe_cycle_count"] <= 3
    assert report["v41_new_real_probe_count"] <= 12
    assert report["v41_new_evidence_count"] >= 6
    assert report["v41_new_real_scored_count"] >= 6
    assert report["cumulative_real_scored_count"] >= 12
    assert report["calibration_tier"] == "EARLY_SAMPLE"
    assert report["live_trading_readiness_claim"] is False
