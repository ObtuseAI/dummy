from __future__ import annotations

from predator_mesh.v38.reports import DEFAULT_REQUIRED_REPORT_NAMES, V38ReportFactory


def test_v38_required_report_manifest_contains_completion_artifacts() -> None:
    reports = V38ReportFactory(env={}).build()
    missing = sorted(set(DEFAULT_REQUIRED_REPORT_NAMES) - set(reports))
    assert missing == []
    assert "final_report_v38.json" not in DEFAULT_REQUIRED_REPORT_NAMES
    assert "dashboard_v38_report_v1.json" in DEFAULT_REQUIRED_REPORT_NAMES
    assert "v38_api_surface_report_v1.json" in DEFAULT_REQUIRED_REPORT_NAMES
    assert "v38_dashboard_payload_safety_report_v1.json" in DEFAULT_REQUIRED_REPORT_NAMES
