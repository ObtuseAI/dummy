from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v34_change_review_and_qc_confirmation_v2_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v34_change_review_and_qc_confirmation_v2_status"] == "PASS"
    assert report["dispatch_overlap_fix_verified"] is True
    assert report["dead_constant_removal_verified"] is True
    assert report["gate_logic_delegates_to_v33"] is True
    assert report["backend_route_registration_verified"] is True
    assert report["no_v8_to_v33_regression_changes"] is True
    assert report["execution_bridge_present"] is False


def test_v34_changed_files_inventoryed() -> None:
    report = assert_current_test_report(__file__)
    assert "predator_mesh/v34/reports.py" in report["changed_files"]
    assert "predator_mesh/v34/run.py" in report["changed_files"]
