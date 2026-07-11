from __future__ import annotations

from archive.report_scripts.generate_v10_reports import generate_dummy_canonical_identity_report_v10


def test_dummy_canonical_identity_v10() -> None:
    report = generate_dummy_canonical_identity_report_v10()
    assert report["verdict"] == "PASS"
    assert report["project"] == "Dummy"
    assert report["active_root"].endswith("dummy")
