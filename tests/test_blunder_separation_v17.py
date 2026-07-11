from __future__ import annotations


def test_blunder_separation_v17_report_passes() -> None:
    from archive.report_scripts.generate_v17_reports import generate_blunder_separation_recheck_v17

    report = generate_blunder_separation_recheck_v17()
    assert report["canonical_blunder_modified"] is False
    assert report["verdict"] == "PASS"
