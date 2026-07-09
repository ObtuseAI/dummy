from __future__ import annotations

from tests.v43_test_helpers import assert_current_test_report


def test_source_truth_v24_stability_window_report() -> None:
    assert_current_test_report(__file__)
