from tests.v29_test_helpers import assert_v29_report_named, v29_reports


def test_v29_required_report_manifest_contains_all_attachment_artifacts() -> None:
    final = assert_v29_report_named(
        "final_report_v29.json",
        "required_report_count",
        "report_paths",
        "all_required_reports_generated",
    )
    reports = v29_reports()

    assert final["required_report_count"] >= 170
    assert final["all_required_reports_generated"] is True
    assert final["missing_required_reports"] == []
    assert len(final["report_paths"]) >= final["required_report_count"]
    assert "oss_candidate_universe_normalizer_v1_report.json" in reports
    assert "dummy_canonical_identity_report_v29.json" in reports
    assert "dashboard_v29_report_v1.json" in reports
