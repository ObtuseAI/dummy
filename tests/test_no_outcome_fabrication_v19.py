from __future__ import annotations


def test_no_outcome_fabrication_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_no_outcome_fabrication_report_v19

    report = generate_no_outcome_fabrication_report_v19()
    assert report["fabricated_outcomes"] is False
    assert report["verdict"] == "PASS"
