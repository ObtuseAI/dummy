from __future__ import annotations

from tests.v38_test_helpers import assert_current_test_report


def test_v37_still_passes_or_partial_expected_v38() -> None:
    report = assert_current_test_report(__file__)
    assert report["v37_still_passes_or_partial_expected_v38_status"] == "PASS"
    assert report["v37_final_verdict"] in {"PASS", "PARTIAL"}
    assert report["v36_carried_status"] in {"PASS", "PASS_OR_PARTIAL_EXPECTED"}
    assert report["blunder_separation_status"] == "PASS"
    assert report["canonical_identity_intact"] is True
