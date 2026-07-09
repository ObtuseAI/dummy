from __future__ import annotations

from predator_mesh.v34.run import ProbeReconciliationToScoreCompoundingControlPlaneV18, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_compounding_control_plane_default_status() -> None:
    plane = ProbeReconciliationToScoreCompoundingControlPlaneV18().build(build_default_v34_state(enable_network=False))

    assert plane.compounding_v18_status == "PASS"
    assert plane.execution_bridge_present is False
    assert plane.next_bundle_recommendation.startswith("DUMMY_V35_")


def test_compounding_control_plane_report_contract() -> None:
    report = assert_v34_report_named(
        "probe_reconciliation_to_score_compounding_control_plane_v18_report.json",
        "probe_reconciliation_to_score_compounding_control_plane_v18_status",
    )

    assert report["probe_reconciliation_to_score_compounding_control_plane_v18_status"] == "PASS"
    assert report["next_bundle_recommendation_v34"].startswith("DUMMY_V35_")
