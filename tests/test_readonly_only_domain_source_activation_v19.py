from __future__ import annotations


def test_readonly_only_domain_source_activation_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_readonly_only_domain_source_activation_report_v19

    report = generate_readonly_only_domain_source_activation_report_v19()
    assert report["read_only_only"] is True
    assert report["write_endpoints_called"] == []
