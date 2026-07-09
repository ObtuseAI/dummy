from __future__ import annotations
from tests.v46_test_helpers import assert_current_test_report
def test_no_duplicate_evidence_scored_as_new_v46_report() -> None:
    assert_current_test_report(__file__)
