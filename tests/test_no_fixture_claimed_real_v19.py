from __future__ import annotations


def test_no_fixture_claimed_real_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_no_fixture_claimed_real_report_v19

    report = generate_no_fixture_claimed_real_report_v19()
    assert report["fixture_evidence_claimed_real"] is False
    assert report["verdict"] == "PASS"
