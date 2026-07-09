from tests.v29_test_helpers import assert_v29_report_named


def test_domain_market_class_scoreboard_v14_summarizes_oss_specs_and_remaining_blockers() -> None:
    report = assert_v29_report_named(
        "domain_market_class_scoreboard_v14_report.json",
        "market_class_scoreboard_v14_status",
        "category_counts",
        "adapter_spec_ready_count",
        "public_probe_ready_count",
    )

    assert report["market_class_scoreboard_v14_status"] == "PASS_PARTIAL_EXPECTED"
    assert report["category_counts"]["weather"] >= 43
    assert report["category_counts"]["sports"] >= 55
    assert report["adapter_spec_ready_count"] >= 5
    assert report["public_probe_ready_count"] >= 3
    assert report["example_market_canonical_center"] is False
    assert report["live_scored_count"] == 0
    assert report["mission_state_verdict"] == "PARTIAL"
