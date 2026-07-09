from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_v40_still_passes_or_partial_expected_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["v40_still_passes_or_partial_expected_v41_status"] == "PASS"
    assert report["v40_carried_status"] == "PASS"
    assert report["canonical_identity_intact"] is True
