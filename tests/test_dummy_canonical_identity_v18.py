from __future__ import annotations


def test_dummy_canonical_identity_v18_report_passes() -> None:
    from archive.report_scripts.generate_v18_reports import generate_dummy_canonical_identity_report_v18

    report = generate_dummy_canonical_identity_report_v18()
    assert report["canonical_name"] == "Dummy"
    assert report["renamed"] is False
