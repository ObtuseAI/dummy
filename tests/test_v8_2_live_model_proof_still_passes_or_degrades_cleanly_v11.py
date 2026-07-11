from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_v8_2_live_model_proof_status_report_v11


def test_v8_2_live_model_proof_still_passes_or_degrades_cleanly_v11() -> None:
    report = generate_v8_2_live_model_proof_status_report_v11()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["status"] in {"LIVE_PROVEN", "PROVIDER_DEGRADED", "UNKNOWN"}
