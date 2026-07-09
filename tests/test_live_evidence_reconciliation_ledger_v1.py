from __future__ import annotations

from predator_mesh.v34.run import LiveEvidenceReconciliationLedgerV1, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_live_evidence_reconciliation_ledger_default_disabled_has_zero_packets() -> None:
    state = build_default_v34_state(enable_network=False)

    assert state["live_public_evidence_ingestion"].live_public_evidence_ingestion_status == "PASS_DISABLED_BY_DEFAULT"
    assert state["live_public_evidence_ingestion"].packet_count == 0
    assert state["live_public_evidence_ingestion"].fixture_promoted_to_live is False


def test_live_evidence_reconciliation_ledger_enabled_packets_include_required_fields() -> None:
    state = build_default_v34_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    ingestion = LiveEvidenceReconciliationLedgerV1().ingest(state["minimal_live_public_probe_execution"])

    assert ingestion.live_public_evidence_ingestion_status == "PASS"
    assert ingestion.packet_count == 3
    packet = ingestion.packets[0]
    assert packet.source_mode == "LIVE_PUBLIC_PROBE_RESULT"
    assert packet.evidence_role == "OBSERVATION"
    assert packet.freshness == "FRESH"
    assert packet.execution_bridge_present is False


def test_live_evidence_reconciliation_ledger_report_contract() -> None:
    report = assert_v34_report_named("live_evidence_reconciliation_ledger_v1_report.json", "live_public_evidence_ingestion_status")

    assert report["live_public_evidence_ingestion_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_public_evidence_packet_count"] == 0
