from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report


def test_no_fuzzy_ack_probe_run_v39() -> None:
    report = assert_current_test_report(__file__)
    assert report["fuzzy_ack_probe_run"] is False

