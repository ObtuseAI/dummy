from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_blunder_separation_recheck_v12


def test_blunder_separation_v12() -> None:
    report = generate_blunder_separation_recheck_v12()

    assert report["verdict"] == "PASS"
    assert report["manifest_matches"] is True
