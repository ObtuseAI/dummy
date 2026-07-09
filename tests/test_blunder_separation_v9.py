from __future__ import annotations

from scripts.generate_v9_reports import generate_blunder_separation_recheck_v9


def test_blunder_separation_v9_passes() -> None:
    report = generate_blunder_separation_recheck_v9()
    assert report["verdict"] == "PASS"
    assert report["manifest_matches"] is True
