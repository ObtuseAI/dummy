from __future__ import annotations


def test_blunder_separation_v16_report_passes() -> None:
    from scripts.generate_v16_reports import generate_blunder_separation_recheck_v16

    report = generate_blunder_separation_recheck_v16()
    assert report["verdict"] == "PASS"
    assert report["canonical_blunder_modified"] is False
