from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v44_test_helpers import ObserverScaleoutReadOnlyTransport, v44_reports


def test_source_rotation_engine_keeps_lanes_and_sources_bounded() -> None:
    reports = v44_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ObserverScaleoutReadOnlyTransport())
    report = reports["source_rotation_engine_v1_report.json"]
    assert report["source_rotation_status"] == "PASS"
    assert report["source_families_attempted"] == ["weather", "crypto", "public_event_reference"]
    assert report["sports_excluded"] is True
    assert report["browser_calls_allowed"] is False
    assert report["max_requests_per_source_family_per_lane"] == 2
    assert report["v44_new_real_probe_count"] <= 18
    for lane in report["lane_results"]:
        assert lane["probe_count"] <= 6
        assert lane["cycle_count"] <= 2
        assert lane["gate_rechecked_before_lane"] is True
