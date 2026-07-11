from pathlib import Path


def test_dashboard_v6_report():
    from archive.report_scripts.generate_v6_reports import generate_dashboard_v6_report
    report = generate_dashboard_v6_report()
    assert report["verdict"] == "PASS"
    assert report["frontend_built"] is True
    for code in report["endpoints"].values():
        if isinstance(code, int):
            assert code == 200


def test_v6_frontend_dist_exists():
    assert (Path("C:/src/engine/dummy/dashboard/frontend/dist/index.html")).exists()
