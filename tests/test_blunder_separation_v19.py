from __future__ import annotations


def test_blunder_separation_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_blunder_separation_recheck_v19

    report = generate_blunder_separation_recheck_v19()
    assert report["canonical_blunder_modified"] is False
    assert report["verdict"] == "PASS"
