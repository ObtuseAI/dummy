import pytest


@pytest.mark.asyncio
async def test_strategy_no_trade_reason_report_v1():
    from archive.report_scripts.generate_v6_reports import generate_strategy_no_trade_reason_report_v1
    report = await generate_strategy_no_trade_reason_report_v1()
    assert report["verdict"] == "PASS"
    assert "reasons" in report
    assert isinstance(report["reasons"], list)
