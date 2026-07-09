from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_v39_still_passes_or_partial_expected_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["v39_still_passes_or_partial_expected_v40_status"] == "PASS"
    assert report["v39_final_verdict"] in {"PASS", "PARTIAL"}
    assert report["blunder_separation_status"] == "PASS"
    assert report["canonical_identity_intact"] is True
