def test_no_order_in_read_only_v3():
    from archive.report_scripts.generate_v6_reports import generate_no_order_in_read_only_report_v3
    report = generate_no_order_in_read_only_report_v3()
    assert report["verdict"] == "PASS"
    assert "create_order" in report["order_creating_methods_blocked"]
    assert "POST" in report["write_http_methods_blocked"]
