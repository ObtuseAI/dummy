def test_live_submit_flag_guard_report_v1():
    from scripts.generate_v6_reports import generate_live_submit_flag_guard_report_v1
    report = generate_live_submit_flag_guard_report_v1()
    assert report["verdict"] == "PASS"
    assert report["enabled"] is False
    assert len(report["block_reasons"]) > 0
