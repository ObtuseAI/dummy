from __future__ import annotations

from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    ProbeRunAuditLedgerV1,
    PublicProbeCacheWriterV1,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_current_test_report, assert_v31_report_named


def test_public_probe_cache_writer_redacts_payloads_and_never_scores_cache() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    packets = LivePublicEvidenceCaptureV1().capture(run)
    cache = PublicProbeCacheWriterV1().write(run, packets)

    assert cache.public_probe_cache_status == "PASS"
    assert cache.cache_record_count == 3
    assert cache.redaction_proof.no_secret_values is True
    assert cache.cached_records_scored_live is False
    assert all(record.raw_payload_redacted is True for record in cache.records)


def test_probe_run_audit_ledger_records_source_and_safety_summary() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)
    audit = ProbeRunAuditLedgerV1().record(run)

    assert audit.probe_run_audit_status == "PASS"
    assert audit.audit_record_count == 1
    assert audit.source_summary["source_family_count"] == 4
    assert audit.outcome_summary["probe_run_count"] == 3
    assert audit.safety_summary["execution_bridge_present"] is False


def test_public_probe_cache_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["public_probe_cache_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["cache_record_count"] == 0
    assert report["cached_records_scored_live"] is False
    audit = assert_v31_report_named("probe_run_audit_ledger_v1_report.json", "probe_run_audit_status")
    assert audit["probe_run_audit_status"] == "PASS_DISABLED_BY_DEFAULT"
