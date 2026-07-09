from __future__ import annotations

from predator_mesh.v33.run import SettlementEvidenceJoinV3, build_default_v33_state
from tests.v33_test_helpers import assert_v33_report_named


def test_settlement_evidence_join_default_disabled_has_no_joins() -> None:
    state = build_default_v33_state(enable_network=False)

    assert state["settlement_evidence_join"].settlement_evidence_join_status == "PASS_DISABLED_BY_DEFAULT"
    assert state["settlement_evidence_join"].compatible_count == 0


def test_settlement_evidence_join_enabled_joins_live_public_only() -> None:
    state = build_default_v33_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    join = SettlementEvidenceJoinV3().join(state["live_public_evidence_ingestion"])

    assert join.settlement_evidence_join_status == "PASS"
    assert join.compatible_count == 3
    assert all(decision.decision == "SETTLEMENT_COMPATIBLE" for decision in join.join_decisions)
    assert all(decision.execution_bridge_present is False for decision in join.join_decisions)


def test_settlement_evidence_join_report_contract() -> None:
    report = assert_v33_report_named("settlement_evidence_join_v3_report.json", "settlement_evidence_join_status")

    assert report["settlement_evidence_join_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["settlement_compatible_evidence_count"] == 0
