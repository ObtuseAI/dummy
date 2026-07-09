from __future__ import annotations

from predator_mesh.v32.recovery import (
    LivePublicEvidenceExpansionV2,
    SettlementCompatibleEvidenceExpansionV2,
    build_default_v32_state,
)
from tests.v32_test_helpers import assert_v32_report_named


def test_settlement_compatible_evidence_expansion_joins_only_live_public_evidence() -> None:
    state = build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    evidence = LivePublicEvidenceExpansionV2().expand(state)
    settlement = SettlementCompatibleEvidenceExpansionV2().expand(evidence)

    assert settlement.settlement_compatible_evidence_expansion_status == "PASS"
    assert settlement.compatible_count == 3
    assert all(decision.live_score_allowed is False for decision in settlement.join_decisions)
    assert settlement.execution_bridge_present is False


def test_settlement_compatible_evidence_expansion_report_contract() -> None:
    report = assert_v32_report_named(
        "settlement_compatible_evidence_expansion_v2_report.json",
        "settlement_compatible_evidence_expansion_status",
    )
    assert report["settlement_compatible_evidence_expansion_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["settlement_compatible_evidence_count"] == 0
