from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_implementation_partial_reduction_v1_reduces_spec_not_implementation_but_preserves_live_blockers() -> None:
    report = assert_v30_report_named(
        "adapter_implementation_partial_reduction_v1_report.json",
        "adapter_implementation_partial_reduction_status",
        "partial_causes_before",
        "partial_causes_after",
    )

    assert report["adapter_implementation_partial_reduction_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert report["partial_causes_before"]["SPEC_NOT_IMPLEMENTED"] >= 1
    assert report["partial_causes_after"]["SPEC_NOT_IMPLEMENTED"] == 0
    assert report["partial_causes_after"]["NO_LIVE_PUBLIC_EVIDENCE"] >= 1
    assert report["partial_causes_after"]["INTEGRATION_DISABLED_BY_DEFAULT"] >= 1
