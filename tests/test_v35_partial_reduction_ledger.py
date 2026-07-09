from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v35_partial_reduction_ledger_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_partial_reduction_ledger_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert "FRONTEND_BUILD_NOT_RUN" in report["partial_causes_before"]
    assert "FRONTEND_BUILD_NOT_RUN" not in report["partial_causes_after"]
    assert "V34_DISPATCH_OVERLAP_FINDING" not in report["partial_causes_after"]
    assert "V34_DEAD_CONSTANT_FINDING" not in report["partial_causes_after"]
    assert report["pass_delta"]["frontend_build_resolved"] == 1
    assert report["execution_bridge_present"] is False
