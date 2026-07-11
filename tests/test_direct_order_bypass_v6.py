def test_direct_order_bypass_v6():
    from archive.report_scripts.generate_v6_reports import generate_firewall_rehearsal_regression_report_v3
    report = generate_firewall_rehearsal_regression_report_v3()
    assert report["verdict"] == "PASS"
    assert report["only_allowed_callers"] is True
    allowed = set(report["allowed_callers"])
    offenders = set(report["files_with_create_order_calls"])
    assert offenders <= allowed
