def test_no_secret_leak_v5():
    from archive.report_scripts.generate_v6_reports import generate_no_secret_leak_report_v5
    report = generate_no_secret_leak_report_v5()
    assert report["verdict"] == "PASS"
    assert report["sample_values_redacted"] is True
