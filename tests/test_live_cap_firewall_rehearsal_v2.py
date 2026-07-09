import pytest
import asyncio


def test_firewall_rehearsal_report_passes():
    from scripts.generate_v5_reports import generate_firewall_rehearsal_report_v2
    report = asyncio.run(generate_firewall_rehearsal_report_v2())
    assert report["verdict"] == "PASS"
    assert report["all_block_tests_passed"] is True
    assert report["live_submit_enabled"] is False


def test_autonomous_live_capped_path_report():
    from scripts.generate_v5_reports import generate_autonomous_live_capped_path_report_v2
    report = generate_autonomous_live_capped_path_report_v2()
    assert report["stops_before_submit"] is True
    assert report["market_orders_blocked"] is True
    assert report["all_orders_through_firewall_submit"] is True
