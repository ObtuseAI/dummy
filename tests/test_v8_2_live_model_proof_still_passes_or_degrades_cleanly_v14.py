from __future__ import annotations

from scripts.generate_v14_reports import generate_v8_2_live_model_proof_status_report_v14


def test_v8_2_live_model_proof_still_passes_or_degrades_cleanly_v14() -> None:
    report = generate_v8_2_live_model_proof_status_report_v14()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["acceptable_degradation"] is True
