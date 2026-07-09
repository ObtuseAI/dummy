from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_report_transform_consistency_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["final_report_consistent"] is True
    assert report["tests_summary_includes_v34"] is True
    assert report["required_manifest_matches"] is True
    assert report["no_missing_artifacts"] is True
    assert report["no_v33_leakage"] is True
    assert report["dispatch_fix_prevents_contamination"] is True
    assert report["execution_bridge_present"] is False
