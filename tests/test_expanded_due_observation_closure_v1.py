from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_expanded_due_observation_closure_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["expanded_due_observation_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["forecast_mutation_performed"] is False
    assert report["outcome_fabricated"] is False


def test_expanded_due_observation_closure_v1_enabled() -> None:
    report = v40_enabled_reports()["expanded_due_observation_closure_v1_report.json"]
    assert report["expanded_due_observation_status"] == "PASS_EXPANDED_DUE_OBSERVATION_CLOSURE"
    assert report["v40_new_observed_count"] > 0
