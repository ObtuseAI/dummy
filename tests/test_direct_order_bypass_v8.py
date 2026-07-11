def test_direct_order_bypass_v8():
    from archive.report_scripts.generate_v8_identity_reports import generate_direct_order_bypass_report_v8

    report = generate_direct_order_bypass_report_v8()
    assert report["verdict"] == "PASS"
    assert report["only_allowed_callers"] is True
    assert report["only_allowed_caller_qualnames"] is True

    allowed = set(report["allowed_callers"])
    offenders = set(report["files_with_create_order_calls"])
    assert offenders <= allowed

    allowed_qualnames = set(report["allowed_caller_qualnames"])
    qualnames = {c["qualname"] for c in report["create_order_callers"]}
    assert qualnames <= allowed_qualnames
