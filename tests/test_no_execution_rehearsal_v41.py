from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_execution_rehearsal_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["execution_rehearsal_created"] is False
