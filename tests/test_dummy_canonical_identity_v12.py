from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_dummy_canonical_identity_report_v12


def test_dummy_canonical_identity_v12() -> None:
    report = generate_dummy_canonical_identity_report_v12()

    assert report["verdict"] == "PASS"
    assert "dummy" in report["cwd"].lower()
