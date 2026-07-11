from __future__ import annotations


def test_v8_2_live_model_proof_still_passes_or_degrades_cleanly_v17() -> None:
    from archive.report_scripts.generate_v17_reports import generate_prior_statuses_v17

    status = generate_prior_statuses_v17()
    assert status["v8_2_live_model_proof_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
    assert status["v8_2_live_model_degraded_cleanly"] is True
