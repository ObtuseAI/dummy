from __future__ import annotations
from tests.v46_test_helpers import assert_current_test_report
def test_v45_still_passes_or_partial_expected_v46_report() -> None:
    assert_current_test_report(__file__)
