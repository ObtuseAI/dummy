from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v39.reports import V39ReportFactory
from tests.v39_test_helpers import RepresentativeReadOnlyTransport, assert_current_test_report


def test_v39_operator_approved_run_controller_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["operator_approval_scope"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["rejects_live_trading_scope"] is True
    assert report["run_mode_decision"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["real_probe_run_count"] == 0
    assert report["operator_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"


def test_v39_exact_gate_with_injected_readonly_transport_closes_first_score() -> None:
    reports = V39ReportFactory(
        env=EXACT_GATE_ENV,
        enable_real_probe=True,
        real_transport=RepresentativeReadOnlyTransport(),
    ).build()
    report = reports["v39_operator_approved_run_controller_v1_report.json"]
    assert report["run_mode_decision"] == "PASS_OPERATOR_APPROVED_READONLY_RUN"
    assert report["real_probe_run_count"] > 0
    assert report["real_evidence_count"] > 0
    assert report["settlement_compatible_evidence_count"] > 0
    assert report["real_observed_count"] > 0
    assert report["real_scored_count"] > 0
