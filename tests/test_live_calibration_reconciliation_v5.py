from __future__ import annotations

from predator_mesh.v34.run import LiveCalibrationReconciliationV5, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_live_calibration_reconciliation_default_disabled_has_no_samples() -> None:
    state = build_default_v34_state(enable_network=False)
    calibration = state["live_calibration_observation_run"]

    assert calibration.live_calibration_observation_status == "PASS_DISABLED_BY_DEFAULT"
    assert calibration.live_calibration_sample_count == 0
    assert calibration.execution_bridge_present is False


def test_live_calibration_reconciliation_enabled_warns_low_sample() -> None:
    state = build_default_v34_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    calibration = LiveCalibrationReconciliationV5().calibrate(state["live_score_observation_run"])

    assert calibration.live_calibration_observation_status == "PASS_LOW_SAMPLE_WARNING"
    assert calibration.live_calibration_sample_count == 3
    assert calibration.low_sample_warning is True


def test_live_calibration_reconciliation_report_contract() -> None:
    report = assert_v34_report_named("live_calibration_reconciliation_v5_report.json", "live_calibration_observation_status")

    assert report["live_calibration_observation_status"] == "PASS_DISABLED_BY_DEFAULT"
