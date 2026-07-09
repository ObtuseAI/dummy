from tests.v29_test_helpers import assert_v29_report_named


def test_settlement_gap_adapter_mapper_v1_maps_unresolved_states_without_speculative_closure() -> None:
    report = assert_v29_report_named(
        "settlement_gap_adapter_mapper_v1_report.json",
        "settlement_gap_adapter_mapper_status",
        "settlement_gap_closure_candidate_count",
        "mapped_blockers",
    )

    assert report["settlement_gap_adapter_mapper_status"] == "PASS"
    assert report["settlement_gap_closure_candidate_count"] >= 3
    assert {
        "SOURCE_UNAVAILABLE",
        "SETTLEMENT_AMBIGUOUS",
        "NOT_DUE_YET",
        "CONTRADICTION_LOW_CONFIDENCE",
        "MANUAL_IMPORT_REQUIRED",
    } <= set(report["mapped_blockers"])
    assert report["speculative_closure_claimed"] is False
    assert report["paid_feed_global_blocker"] is False
    assert report["browser_automation_added"] is False
