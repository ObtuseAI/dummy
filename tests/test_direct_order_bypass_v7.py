def test_direct_order_bypass_v7():
    from scripts.generate_v7_reports import generate_direct_order_bypass_report_v7
    report = generate_direct_order_bypass_report_v7()
    assert report["verdict"] == "PASS"
    assert report["only_allowed_callers"] is True
    allowed = set(report["allowed_callers"])
    offenders = set(report["files_with_create_order_calls"])
    assert offenders <= allowed
