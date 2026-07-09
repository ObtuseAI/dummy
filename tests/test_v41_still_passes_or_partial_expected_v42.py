from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_v41_still_passes_or_partial_expected_v42() -> None:
    report = assert_current_test_report(__file__)
    assert report["v41_still_passes_or_partial_expected_v42_status"] == "PASS"
    assert report["v41_carried_status"] == "PASS"
    assert report["canonical_identity_intact"] is True
