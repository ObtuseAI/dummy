from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_dummy_canonical_identity_report_v14


def test_dummy_canonical_identity_v14_report_passes() -> None:
    report = generate_dummy_canonical_identity_report_v14()

    assert report["canonical_name"] == "Dummy"
    assert report["verdict"] == "PASS"
