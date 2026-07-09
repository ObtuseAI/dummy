from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v41.reports import V41ReportFactory
from tests.v41_test_helpers import MultiCycleReadOnlyTransport, assert_current_test_report


def test_bounded_real_public_probe_expansion_v2_budget_and_gate() -> None:
    report = assert_current_test_report(__file__)
    assert report["real_probe_run_allowed"] is False
    assert report["max_cycles"] == 3
    assert report["max_total_requests"] == 12
    enabled = V41ReportFactory(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=MultiCycleReadOnlyTransport()).build()
    enabled_report = enabled["bounded_real_public_probe_expansion_v2_report.json"]
    assert enabled_report["real_probe_run_allowed"] is True
    assert enabled_report["v41_probe_cycle_count"] == 2
    assert enabled_report["v41_new_real_probe_count"] == 6
    assert enabled_report["sports_excluded"] is True
