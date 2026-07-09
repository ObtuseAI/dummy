from __future__ import annotations

from scripts.generate_v9_reports import generate_direct_order_bypass_report_v9


def test_direct_order_bypass_report_v9_passes() -> None:
    report = generate_direct_order_bypass_report_v9()
    assert report["verdict"] == "PASS"
    assert report["unexpected_caller_qualnames"] == []
