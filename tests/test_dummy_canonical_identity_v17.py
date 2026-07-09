from __future__ import annotations


def test_dummy_canonical_identity_v17_report_passes() -> None:
    from scripts.generate_v17_reports import generate_dummy_canonical_identity_report_v17

    report = generate_dummy_canonical_identity_report_v17()
    assert report["canonical_name"] == "Dummy"
    assert report["verdict"] == "PASS"
