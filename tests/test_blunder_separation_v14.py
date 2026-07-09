from __future__ import annotations

from scripts.generate_v14_reports import generate_blunder_separation_recheck_v14


def test_blunder_separation_v14_report_passes() -> None:
    report = generate_blunder_separation_recheck_v14()

    assert report["verdict"] == "PASS"
    assert report["dummy_blunder_confused"] is False
