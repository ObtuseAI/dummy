from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v43.reports import V43ReportFactory
from tests.v43_test_helpers import DevelopingReadOnlyTransport


def test_v43_controller_default_blocks_without_gate() -> None:
    reports = V43ReportFactory().build()
    report = reports["v43_developing_sample_pursuit_controller_v1_report.json"]
    assert report["developing_sample_pursuit_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v42_cumulative_real_scored_count"] >= 18
    assert report["v43_new_real_scored_count"] == 0
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v43_enabled_reaches_developing_sample_without_trading_readiness() -> None:
    reports = V43ReportFactory(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=DevelopingReadOnlyTransport()).build()
    report = reports["v43_developing_sample_pursuit_controller_v1_report.json"]
    assert report["developing_sample_pursuit_status"] == "PASS_DEVELOPING_SAMPLE_PURSUIT"
    assert 1 <= report["v43_optional_sample_cycle_count"] <= 3
    assert 7 <= report["v43_new_real_scored_count"] <= 12
    assert 25 <= report["cumulative_real_scored_count"] <= 30
    assert report["developing_sample_threshold_decision"] == "PASS_DEVELOPING_SAMPLE_THRESHOLD_MET"
    assert report["calibration_tier_after"] == "DEVELOPING_SAMPLE"
    assert report["live_trading_readiness_claim"] is False
