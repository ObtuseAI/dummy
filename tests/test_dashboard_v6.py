from pathlib import Path


def test_dashboard_v6_report(monkeypatch):
    from archive.report_scripts.generate_v6_reports import generate_dashboard_v6_report
    from archive.routes import v6_routes

    # The archive report must remain an offline/status contract. Never let
    # workstation credentials turn this unit test into a broker read.
    monkeypatch.setattr(v6_routes, "_credentials_present", lambda: False)
    report = generate_dashboard_v6_report()
    assert report["verdict"] == "PASS"
    assert report["frontend_built"] is True
    assert report["archive_surface"] == "offline_archive"
    assert report["operator_guard_verified"] is True
    assert report["endpoints"] == report["expected_statuses"]


def test_v6_frontend_dist_exists():
    assert (Path("C:/src/engine/dummy/dashboard/frontend/dist/index.html")).exists()
