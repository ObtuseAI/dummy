from __future__ import annotations

from archive.report_scripts.generate_v10_reports import generate_blunder_separation_recheck_v10


def test_blunder_separation_v10() -> None:
    report = generate_blunder_separation_recheck_v10()
    assert report["verdict"] == "PASS"
    assert report["manifest_matches"] is True
