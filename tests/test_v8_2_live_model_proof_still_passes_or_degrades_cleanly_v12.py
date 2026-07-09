from __future__ import annotations

from scripts.generate_v12_reports import generate_v8_2_live_model_proof_status_report_v12


def test_v8_2_live_model_proof_still_passes_or_degrades_cleanly_v12() -> None:
    report = generate_v8_2_live_model_proof_status_report_v12()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["status"] in {"LIVE_PROVEN", "PROVIDER_DEGRADED", "UNKNOWN"}
