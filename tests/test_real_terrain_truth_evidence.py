from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_real_terrain_truth_evidence_reports_inputs_and_no_secret_values() -> None:
    verdict = pass_truth_verdict()
    report = verdict.evidence.to_report()

    assert report["real_evidence_present"] is True
    assert report["eligible_market_candidate_count"] == 1
    assert report["nonempty_book_proof"] is True
    assert report["secret_values_exposed"] is False
