from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_source_truth_v21_real_sample_growth() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_v21_status"] == "PASS"
    assert report["source_health_from_real_probes_only"] is True
    assert report["evidence_availability_from_real_evidence_only"] is True
    assert report["settlement_usefulness_from_real_joins_only"] is True
    assert report["score_truth_from_real_scores_only"] is True
    assert report["source_truth_to_execution_bridge_present"] is False
