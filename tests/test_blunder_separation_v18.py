from __future__ import annotations


def test_blunder_separation_v18_report_passes() -> None:
    from archive.report_scripts.generate_v18_reports import generate_blunder_separation_recheck_v18

    report = generate_blunder_separation_recheck_v18()
    assert report["canonical_blunder_modified"] is False
    assert report["verdict"] == "PASS"
