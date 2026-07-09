from predator_mesh.v30.adapters import AdapterObservationClosureDryRunV1, build_default_v30_context
from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_observation_closure_dry_run_v1_keeps_fixture_pipeline_non_scoring() -> None:
    result = AdapterObservationClosureDryRunV1().run(build_default_v30_context())

    assert result["dry_run_observed_count"] >= 4
    assert result["dry_run_score_eligible_count"] == 0
    assert result["live_scored_count"] == 0
    assert result["unresolved_forecast_scored"] is False
    assert result["ambiguous_settlement_scored"] is False
    assert result["source_unavailable_forecast_scored"] is False
    assert result["not_due_forecast_scored"] is False
    assert result["outcome_fabricated"] is False


def test_adapter_observation_closure_dry_run_v1_report_contract() -> None:
    report = assert_v30_report_named("adapter_observation_closure_dry_run_v1_report.json", "observation_closure_dry_run_status")
    assert report["observation_closure_dry_run_status"] == "PASS_PIPELINE_ONLY"
    assert report["dry_run_score_eligible_count"] == 0
