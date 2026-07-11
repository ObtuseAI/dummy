from __future__ import annotations


def test_dummy_canonical_identity_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_dummy_canonical_identity_report_v19

    report = generate_dummy_canonical_identity_report_v19()
    assert report["canonical_name"] == "Dummy"
    assert report["renamed"] is False
