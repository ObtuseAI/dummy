from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_fuzzy_ack_probe_run_v42() -> None:
    assert_current_test_report(__file__)["fuzzy_ack_probe_run"] is False
