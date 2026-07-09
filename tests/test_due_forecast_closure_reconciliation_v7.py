from __future__ import annotations

from predator_mesh.v34.run import DueForecastClosureReconciliationV7, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_due_forecast_closure_reconciliation_default_disabled_preserves_blockers() -> None:
    state = build_default_v34_state(enable_network=False)
    observation = state["due_forecast_observation_run"]

    assert observation.due_forecast_observation_run_status == "PASS_DISABLED_BY_DEFAULT"
    assert observation.due_forecast_count == 4
    assert observation.observed_forecast_count == 0
    assert observation.live_unresolved_count == 4
    assert "PROBE_DISABLED" in observation.blockers


def test_due_forecast_closure_reconciliation_enabled_observes_matching_evidence() -> None:
    state = build_default_v34_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    observation = DueForecastClosureReconciliationV7().observe(state["settlement_evidence_join"], gate_enabled=True)

    assert observation.due_forecast_observation_run_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert observation.observed_forecast_count == 3
    assert observation.live_unresolved_count == 1
    assert "SETTLEMENT_AMBIGUOUS" in observation.blockers
    assert all(decision.outcome_fabricated is False for decision in observation.decisions)


def test_due_forecast_closure_reconciliation_report_contract() -> None:
    report = assert_v34_report_named("due_forecast_closure_reconciliation_v7_report.json", "due_forecast_observation_run_status")

    assert report["due_forecast_observation_run_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["observed_forecast_count"] == 0
