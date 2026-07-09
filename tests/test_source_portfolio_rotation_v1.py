from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from tests.v45_test_helpers import ObserverContinuationReadOnlyTransport, v45_reports


def test_source_portfolio_rotation_keeps_sources_bounded_and_contained() -> None:
    reports = v45_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ObserverContinuationReadOnlyTransport())
    report = reports["source_portfolio_rotation_v1_report.json"]
    assert report["source_portfolio_status"] == "PASS"
    assert report["source_families_attempted"] == ["weather", "crypto", "public_event_reference"]
    assert report["sports_excluded"] is True
    assert report["browser_calls_allowed"] is False
    assert report["max_requests_per_source_family_per_lane"] == 2
    assert report["v45_new_real_probe_count"] <= 30
    for lane in report["lane_results"]:
        assert lane["probe_count"] <= 6
        assert lane["cycle_count"] <= 2
        assert lane["failure_containment_status"] == "PASS"
        assert lane["gate_rechecked_before_lane"] is True
