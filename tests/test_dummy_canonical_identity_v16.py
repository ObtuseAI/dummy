from __future__ import annotations


def test_dummy_canonical_identity_v16_report_passes() -> None:
    from scripts.generate_v16_reports import generate_dummy_canonical_identity_report_v16

    report = generate_dummy_canonical_identity_report_v16()
    assert report["canonical_name"] == "Dummy"
    assert report["verdict"] == "PASS"
