from __future__ import annotations

from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_v31_report_named


def _enabled_run():
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    return V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)


def test_live_public_evidence_capture_accepts_only_enabled_probe_results() -> None:
    disabled_gate = ExplicitPublicProbeOperatorGateV3().decide({})
    disabled_run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(disabled_gate)
    assert LivePublicEvidenceCaptureV1().capture(disabled_run) == []

    packets = LivePublicEvidenceCaptureV1().capture(_enabled_run())

    assert len(packets) == 3
    assert all(packet.mode == "LIVE_PUBLIC_PROBE_RESULT" for packet in packets)
    assert all(packet.live_observation_eligible is True for packet in packets)
    assert all(packet.live_score_eligible is False for packet in packets)
    assert all(packet.execution_bridge_present is False for packet in packets)
    assert all(packet.raw_payload_redacted is True for packet in packets)


def test_live_public_evidence_capture_report_contract() -> None:
    report = assert_v31_report_named("live_public_evidence_capture_v1_report.json", "live_public_evidence_capture_status")
    assert report["live_public_evidence_capture_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["live_public_evidence_packet_count"] == 0
    assert report["fixtures_promoted_to_live_public"] is False
