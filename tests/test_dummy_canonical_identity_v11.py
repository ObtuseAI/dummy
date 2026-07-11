from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_dummy_canonical_identity_report_v11


def test_dummy_canonical_identity_v11() -> None:
    report = generate_dummy_canonical_identity_report_v11()
    assert report["verdict"] == "PASS"
    assert report["project"] == "Dummy"
    assert report["active_root"].endswith("dummy")
