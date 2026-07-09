from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_real_due_observation_closure_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["real_due_observation_closure_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["outcome_fabricated"] is False
    assert report["forecast_mutation_performed"] is False


def test_real_due_observation_closure_enabled_path() -> None:
    report = v39_enabled_reports()["real_due_observation_closure_v2_report.json"]
    assert report["real_due_observation_closure_status"] == "PASS_REAL_DUE_OBSERVATION_CLOSURE"
    assert report["real_observed_count"] > 0
    assert report["observation_mode"] == "OBSERVED_REAL_LIVE_PUBLIC"

