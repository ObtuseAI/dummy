from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_timeout_guards_still_intact_report_v12


def test_timeout_guards_still_intact_v12() -> None:
    report = generate_timeout_guards_still_intact_report_v12()

    assert report["verdict"] == "PASS"
    assert report["max_orderbook_request_timeout_s"] <= 10
    assert report["max_orderbook_adapter_timeout_s"] <= 45
    assert report["recursive_pytest_allowed"] is False
