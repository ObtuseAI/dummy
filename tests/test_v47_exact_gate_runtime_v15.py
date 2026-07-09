from __future__ import annotations

from tests.v47_test_helpers import StableSampleReadOnlyTransport, assert_v47_report_named, v47_reports


def test_exact_gate_runtime_v15_default_fails_closed() -> None:
    report = assert_v47_report_named("exact_gate_runtime_v15_report.json", "exact_gate_runtime_v15_status")
    assert report["exact_gate_runtime_v15_status"] == "PASS_BLOCKED"
    assert report["exact_gate_status"] == "PROBE_DISABLED_BY_DEFAULT"
    assert report["ack_decision"] == "FAIL_MISSING_ACK"
    assert report["v47_new_real_probe_count"] == 0
    assert report["missing_ack_probe_run"] is False


def test_exact_gate_runtime_v15_rejects_fuzzy_or_trading_ack() -> None:
    reports = v47_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY order"},
        enable_real_probe=True,
        real_transport=StableSampleReadOnlyTransport(),
    )
    report = reports["exact_gate_runtime_v15_report.json"]
    assert report["exact_gate_runtime_v15_status"] == "PASS_BLOCKED"
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["trading_language_rejected"] is True
    assert report["v47_new_real_probe_count"] == 0
