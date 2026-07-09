import pytest


@pytest.mark.asyncio
async def test_live_cap_firewall_rehearsal_report_v3():
    from scripts.generate_v6_reports import generate_live_cap_firewall_rehearsal_report_v3
    report = await generate_live_cap_firewall_rehearsal_report_v3()
    assert report["verdict"] == "PASS"
    assert report["live_submitted"] is False
    block_tests = report.get("block_tests", {})
    assert all(block_tests.values())
