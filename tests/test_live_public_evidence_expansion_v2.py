from __future__ import annotations

from predator_mesh.v32.recovery import LivePublicEvidenceExpansionV2, build_default_v32_state
from tests.v32_test_helpers import assert_v32_report_named


def test_live_public_evidence_expansion_disabled_gate_yields_no_packets() -> None:
    expansion = LivePublicEvidenceExpansionV2().expand(build_default_v32_state(enable_network=False))

    assert expansion.live_public_evidence_expansion_status == "PASS_DISABLED_BY_DEFAULT"
    assert expansion.packet_count == 0
    assert expansion.fixture_promoted_to_live is False
    assert expansion.source_unavailable_promoted_to_live is False
    assert expansion.execution_bridge_present is False


def test_live_public_evidence_expansion_enabled_fake_path_captures_three_packets() -> None:
    expansion = LivePublicEvidenceExpansionV2().expand(build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    }))

    assert expansion.live_public_evidence_expansion_status == "PASS"
    assert expansion.packet_count == 3
    assert expansion.family_summary["weather"] == 1
    assert expansion.family_summary["crypto"] == 1
    assert expansion.family_summary["public_event"] == 1


def test_live_public_evidence_expansion_report_contract() -> None:
    report = assert_v32_report_named("live_public_evidence_expansion_v2_report.json", "live_public_evidence_expansion_status")
    assert report["live_public_evidence_expansion_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_public_evidence_packet_count"] == 0
