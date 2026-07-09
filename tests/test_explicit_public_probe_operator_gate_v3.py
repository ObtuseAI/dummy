from __future__ import annotations

from predator_mesh.v31.probes import ExplicitPublicProbeOperatorGateV3
from tests.v31_test_helpers import assert_v31_report_named


def test_public_probe_gate_is_disabled_by_default_and_preserves_config_hashes() -> None:
    decision = ExplicitPublicProbeOperatorGateV3().decide({})

    assert decision.enabled is False
    assert decision.state == "DISABLED_BY_DEFAULT"
    assert decision.reason == "EXPLICIT_OPERATOR_GATE_NOT_SET"
    assert decision.max_requests == 0
    assert decision.timeout_budget_seconds == 0
    assert decision.allowed_adapter_families == []
    assert decision.safety_proof.no_execution_bridge is True
    assert decision.safety_proof.read_only_only is True
    assert decision.config_diff_proof.live_submit_modified is False
    assert decision.config_diff_proof.caps_modified is False
    assert decision.config_diff_proof.live_submit_hash == "3875B81E90B636147CC5BCE5F247B71AD25877C165F4773C98D5C2AD61DB515E"
    assert decision.config_diff_proof.caps_hash == "F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5"


def test_public_probe_gate_enables_only_with_explicit_readonly_ack() -> None:
    decision = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )

    assert decision.enabled is True
    assert decision.state == "ENABLED_READONLY_PUBLIC_PROBES"
    assert decision.reason == "EXPLICIT_OPERATOR_GATE_CONFIRMED"
    assert decision.max_requests == 4
    assert decision.timeout_budget_seconds <= 15
    assert set(decision.allowed_adapter_families) == {"weather", "crypto", "public_event", "kalshi_readonly"}
    assert decision.safety_proof.no_source_api_keys_read is True
    assert decision.safety_proof.no_browser_automation is True
    assert decision.safety_proof.no_live_submit_or_caps_mutation is True


def test_public_probe_gate_reports_disabled_default() -> None:
    report = assert_v31_report_named(
        "explicit_public_probe_operator_gate_v3_report.json",
        "public_probe_operator_gate_status",
    )
    assert report["public_probe_operator_gate_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["public_probe_gate_state"] == "DISABLED_BY_DEFAULT"
    assert report["probe_run_count"] == 0
    assert report["live_scored_count"] == 0
