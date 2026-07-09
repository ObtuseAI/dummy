from __future__ import annotations

from predator_mesh.v14.no_trade_gates import StaleQuoteNoTradeReport


def test_stale_quote_no_trade_report_blocks_old_quotes() -> None:
    report = StaleQuoteNoTradeReport(snapshot_age_ms=4_500, max_age_ms=1_500).to_report()

    assert report["trade_allowed"] is False
    assert report["snapshot_age_ms"] > report["max_age_ms"]
    assert "STALE_QUOTE" in report["no_trade_reasons"]
    assert report["verdict"] == "PASS"
