from __future__ import annotations

from scripts.generate_v11_reports import generate_blunder_separation_recheck_v11


def test_blunder_separation_v11() -> None:
    report = generate_blunder_separation_recheck_v11()
    assert report["verdict"] == "PASS"
    assert report["manifest_matches"] is True
