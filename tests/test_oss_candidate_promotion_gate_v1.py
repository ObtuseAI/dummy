from tests.v29_test_helpers import assert_v29_report_named


def test_oss_candidate_promotion_gate_v1_requires_specs_fixtures_contracts_and_readonly_probe_plans() -> None:
    report = assert_v29_report_named(
        "oss_candidate_promotion_gate_v1_report.json",
        "oss_candidate_promotion_gate_status",
        "promotion_level_counts",
        "promotion_prerequisites",
    )

    assert report["oss_candidate_promotion_gate_status"] == "PASS"
    assert report["promotion_level_counts"]["ADAPTER_SPEC_READY"] >= 5
    assert report["promotion_level_counts"]["REFERENCE_ONLY"] > 0
    assert report["promotion_level_counts"]["BLOCKED_OR_TERMS_GATED"] > 0
    assert report["promotion_prerequisites"] == [
        "license_terms_triage",
        "maintenance_quality_score",
        "market_class_fit",
        "in_house_adapter_spec",
        "fixture_schema",
        "contract_test_plan",
        "public_probe_readiness_or_fixture_only_reason",
    ]
    assert report["promotion_to_live_execution_allowed"] is False
