from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v42.reports import V42ReportFactory
from tests.v42_test_helpers import CalibrationReadOnlyTransport, assert_current_test_report


def test_v42_controller_default_blocks_without_gate() -> None:
    report = assert_current_test_report(__file__)
    assert report["calibration_deepening_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v41_cumulative_real_scored_count"] >= 12
    assert report["v42_new_real_scored_count"] == 0
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v42_enabled_extends_samples_for_calibration_without_trading_readiness() -> None:
    reports = V42ReportFactory(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=CalibrationReadOnlyTransport()).build()
    report = reports["v42_real_calibration_deepening_controller_v1_report.json"]
    assert report["calibration_deepening_status"] == "PASS_REAL_CALIBRATION_DEEPENING"
    assert 1 <= report["v42_optional_sample_cycle_count"] <= 2
    assert 6 <= report["v42_new_real_scored_count"] <= 12
    assert 18 <= report["cumulative_real_scored_count"] <= 24
    assert report["calibration_tier"] == "EARLY_SAMPLE"
    assert report["live_trading_readiness_claim"] is False
