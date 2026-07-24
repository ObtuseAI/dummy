def test_dashboard_v6_report(monkeypatch):
    from archive.report_scripts.generate_v6_reports import generate_dashboard_v6_report
    from archive.routes import v6_routes

    # The archive report must remain an offline/status contract. Never let
    # workstation credentials turn this unit test into a broker read.
    monkeypatch.setattr(v6_routes, "_credentials_present", lambda: False)
    report = generate_dashboard_v6_report()
    assert report["verdict"] == "PASS"
    # Wave-85: the archived v6 verdict no longer depends on a local npm build.
    # dashboard/frontend is frozen archive source with no build tooling, so
    # "was the frontend built" is not a property of the archived surface.
    assert report["frontend_built"] is None
    assert report["frontend_build_status"] == "not_applicable_frozen_archive_source"
    assert report["archive_surface"] == "offline_archive"
    assert report["operator_guard_verified"] is True
    assert report["endpoints"] == report["expected_statuses"]
