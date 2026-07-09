from tests.v30_test_helpers import assert_v30_report_named, v30_reports


def test_v30_required_report_manifest_contains_all_attachment_artifacts() -> None:
    final = assert_v30_report_named(
        "final_report_v30.json",
        "required_report_count",
        "report_paths",
        "all_required_reports_generated",
    )
    reports = v30_reports()

    assert final["required_report_count"] >= 155
    assert final["all_required_reports_generated"] is True
    assert final["missing_required_reports"] == []
    assert "v30_adapter_implementation_selection_v1_report.json" in reports
    assert "dummy_canonical_identity_report_v30.json" in reports
    assert "dashboard_v30_report_v1.json" in reports
