from __future__ import annotations

from scripts.generate_v11_reports import generate_timeout_guards_still_intact_report_v11


def test_timeout_guards_still_intact_v11() -> None:
    report = generate_timeout_guards_still_intact_report_v11()
    assert report["verdict"] == "PASS"
    assert report["max_liquidity_timeout_s"] <= 10
    assert report["max_reconcile_timeout_s"] <= 10
