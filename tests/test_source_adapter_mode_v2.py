from __future__ import annotations

from predator_mesh.v12.source_adapter_closure import SourceAdapterClosurePass


def test_source_adapter_mode_v2_reports_remaining_sample_and_mock_modes_explicitly() -> None:
    report = SourceAdapterClosurePass().mode_report_v2()

    assert report["mode_counts"]["LIVE_PUBLIC_BOUNDED"] >= 2
    assert report["mode_counts"]["SAMPLE_STATIC"] >= 1
    assert report["mode_counts"]["MOCK_ONLY_EXPLICIT"] >= 1
    assert report["verdict"] == "PARTIAL"
