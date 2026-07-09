from __future__ import annotations

from scripts.generate_v9_reports import generate_dummy_canonical_identity_report_v9


def test_dummy_canonical_identity_v9_passes() -> None:
    report = generate_dummy_canonical_identity_report_v9()
    assert report["verdict"] == "PASS"
    assert report["project"] == "Dummy"
    assert report["active_root"].endswith("dummy")
