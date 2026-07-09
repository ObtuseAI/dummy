from __future__ import annotations

from tests.v43_test_helpers import assert_current_test_report


def test_no_duplicate_evidence_scored_as_new_v43_report() -> None:
    assert_current_test_report(__file__)
