from __future__ import annotations

from scripts.generate_v13_reports import generate_dummy_canonical_identity_report_v13


def test_dummy_canonical_identity_v13_report_passes() -> None:
    report = generate_dummy_canonical_identity_report_v13()

    assert report["verdict"] == "PASS"
    assert report["canonical_name"] == "Dummy"
