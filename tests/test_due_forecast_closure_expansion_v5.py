from __future__ import annotations

from predator_mesh.v32.recovery import (
    DueForecastClosureExpansionV5,
    LivePublicEvidenceExpansionV2,
    SettlementCompatibleEvidenceExpansionV2,
    build_default_v32_state,
)
from tests.v32_test_helpers import assert_v32_report_named


def test_due_forecast_closure_expansion_closes_only_matching_live_public_evidence() -> None:
    state = build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    settlement = SettlementCompatibleEvidenceExpansionV2().expand(LivePublicEvidenceExpansionV2().expand(state))
    closure = DueForecastClosureExpansionV5().close(settlement)

    assert closure.due_forecast_closure_expansion_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert closure.due_forecast_count == 4
    assert closure.observed_forecast_count == 3
    assert closure.live_unresolved_count == 1
    assert "SETTLEMENT_AMBIGUOUS" in closure.blockers
    assert closure.outcome_fabricated is False


def test_due_forecast_closure_expansion_report_contract() -> None:
    report = assert_v32_report_named("due_forecast_closure_expansion_v5_report.json", "due_forecast_closure_expansion_status")
    assert report["due_forecast_closure_expansion_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["observed_forecast_count"] == 0
